import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.exceptions import DocumentNotInOneC, OneCUnavailable

log = logging.getLogger(__name__)

SELECT_FIELDS: dict[str, tuple[str, ...]] = {
    "Document_ПеремещениеТоваров": ("Number", "Date"),
    "Document_СчетФактураВыданный": (
        "Number",
        "ПредставлениеНомера",
        "Date",
        "Корректировочный",
        "ДокументОснование",
        "ДокументОснование_Type",
    ),
}

LEGACY_SELECT_FIELDS: dict[str, tuple[str, ...]] = {
    "Document_ПеремещениеТоваров": ("Number", "Date"),
    "Document_СчетФактураВыданный": (
        "Number",
        "ПредставлениеНомера",
        "Date",
        "Корректировочный",
        "ДокументОснование",
        "ДокументОснование_Type",
    ),
}

KNOWN_DOC_TYPES: tuple[str, ...] = (
    "Document_ПеремещениеТоваров",
    "Document_СчетФактураВыданный",
)

MARK_ELIGIBLE_ENTITIES: frozenset[str] = frozenset({"Document_СчетФактураВыданный"})

INVOICE_SYNC_SELECT = (
    "Ref_Key",
    "Number",
    "ПредставлениеНомера",
    "Date",
    "Корректировочный",
    "DeletionMark",
    "ВыставленВЭлектронномВиде",
    "kzvСсылкаНаКопию",
    "ДокументОснование",
    "ДокументОснование_Type",
    "Партнер/Description",
    "Партнер/НаименованиеПолное",
)

INVOICE_SYNC_EXPAND = "Партнер"


def _odata_query(params: dict[str, str]) -> str:
    # 1C OData is sensitive to query encoding in some installations:
    # keep OData syntax characters readable and encode spaces as %20, not "+".
    safe = "$,/'():"
    return "&".join(
        f"{quote(key, safe=safe)}={quote(value, safe=safe)}"
        for key, value in params.items()
    )

PROP_REGISTERED = uuid.UUID("bda8ba09-4787-11f1-92ca-00155d060d01")
PROP_SEALED = uuid.UUID("d034a826-4787-11f1-92ca-00155d060d01")
PROP_VERIFIED = uuid.UUID("daa0fcae-4787-11f1-92ca-00155d060d01")
PROP_INVOICE_SENT_TO_ACCOUNTING = uuid.UUID("7996104c-45ed-11ea-811f-001e67ead229")


@dataclass(frozen=True)
class RelatedRef:
    guid: uuid.UUID
    entity: str


@dataclass(frozen=True)
class RealizationSummary:
    number: str
    doc_date: date


@dataclass
class NormalizedDocument:
    entity: str
    doc_kind: str
    doc_number: str
    doc_date: date
    related_realization_ref: RelatedRef | None
    raw_payload: dict[str, Any]
    partner_name: str | None = None
    related_realization_number: str | None = None
    related_realization_date: date | None = None


def parse_odata_date(s: str | None) -> date:
    if not s:
        raise ValueError("missing Date")
    return datetime.fromisoformat(s).date()


def _extract_related_ref(payload: dict[str, Any]) -> RelatedRef | None:
    raw_type = payload.get("ДокументОснование_Type")
    # In this 1C OData, document refs are exposed as "<Field>" (GUID string),
    # not "<Field>_Key" for Document_* types.
    raw_key = payload.get("ДокументОснование") or payload.get("ДокументОснование_Key")
    if not raw_type or not raw_key:
        return None
    short = raw_type.split(".", 1)[-1]
    if not short.startswith("Document_") or "Реализация" not in short:
        return None
    try:
        guid = uuid.UUID(str(raw_key))
    except (ValueError, AttributeError):
        return None
    return RelatedRef(guid=guid, entity=short)


def extract_related_ref(payload: dict[str, Any]) -> RelatedRef | None:
    return _extract_related_ref(payload)


def normalize_document(entity: str, payload: dict[str, Any]) -> NormalizedDocument:
    partner_name: str | None = None
    if entity == "Document_ПеремещениеТоваров":
        kind = "ПРМ"
        doc_number = str(payload.get("Number", ""))
        receiver = payload.get("СкладПолучатель")
        if isinstance(receiver, dict):
            partner_name = (
                receiver.get("Description")
                or receiver.get("Наименование")
                or receiver.get("НаименованиеПолное")
            )
        related = None
    elif entity == "Document_СчетФактураВыданный":
        kind = "УКД" if payload.get("Корректировочный") else "УПД"
        doc_number = str(payload.get("ПредставлениеНомера") or payload.get("Number", ""))
        related = _extract_related_ref(payload)
        partner = payload.get("Партнер")
        if isinstance(partner, dict):
            partner_name = partner.get("НаименованиеПолное")
        else:
            partner_name = None
    else:
        raise ValueError(f"unknown entity {entity}")
    return NormalizedDocument(
        entity=entity,
        doc_kind=kind,
        doc_number=doc_number,
        doc_date=parse_odata_date(payload.get("Date")),
        related_realization_ref=related,
        raw_payload=payload,
        partner_name=str(partner_name).strip() if partner_name else None,
    )


class OneCClient:
    def __init__(self, *, base_url: str, user: str, password: str, timeout: int = 60):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(user, password),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_document(self, guid: uuid.UUID) -> tuple[str, dict[str, Any]]:
        last_exc: Exception | None = None
        for entity in KNOWN_DOC_TYPES:
            try:
                resp = await self._get_entity(entity, guid)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
                last_exc = e
                continue
            if resp.status_code == 200:
                return entity, resp.json()
            if resp.status_code == 401:
                raise OneCUnavailable("Не удалось авторизоваться в 1С")
            if resp.status_code == 404:
                continue
            raise OneCUnavailable(f"1С вернула неожиданный статус {resp.status_code}")
        if last_exc is not None:
            raise OneCUnavailable("1С недоступна") from last_exc
        raise DocumentNotInOneC("Документ не найден в 1С")

    async def _get_entity(self, entity: str, guid: uuid.UUID) -> httpx.Response:
        params = {"$format": "json", "$select": ",".join(SELECT_FIELDS[entity])}
        url = f"/{entity}(guid'{guid}')"
        resp = await self._client.get(url, params=params)
        if resp.status_code in (400, 501) and entity in LEGACY_SELECT_FIELDS:
            return await self._client.get(
                url,
                params={"$format": "json", "$select": ",".join(LEGACY_SELECT_FIELDS[entity])},
            )
        return resp

    async def lookup_document_with_related(self, guid: uuid.UUID) -> NormalizedDocument:
        entity, payload = await self.fetch_document(guid)
        normalized = normalize_document(entity, payload)
        if entity == "Document_ПеремещениеТоваров":
            receiver_name = await self._get_transfer_receiver_name(entity, guid)
            if receiver_name:
                normalized.partner_name = receiver_name
                raw_receiver = normalized.raw_payload.get("СкладПолучатель")
                if not isinstance(raw_receiver, dict):
                    normalized.raw_payload["СкладПолучатель"] = {}
                    raw_receiver = normalized.raw_payload["СкладПолучатель"]
                raw_receiver["Description"] = receiver_name
        if entity == "Document_СчетФактураВыданный":
            partner_name = await self._get_partner_name(entity, guid)
            if partner_name:
                normalized.partner_name = partner_name
                raw_partner = normalized.raw_payload.get("Партнер")
                if not isinstance(raw_partner, dict):
                    normalized.raw_payload["Партнер"] = {}
                    raw_partner = normalized.raw_payload["Партнер"]
                raw_partner["НаименованиеПолное"] = partner_name
        if normalized.related_realization_ref is not None:
            summary = await self.fetch_related_realization(normalized.related_realization_ref)
            if summary is not None:
                normalized.related_realization_number = summary.number
                normalized.related_realization_date = summary.doc_date
        return normalized

    async def _get_partner_name(self, entity: str, guid: uuid.UUID) -> str | None:
        url = f"/{entity}(guid'{guid}')/Партнер"
        try:
            resp = await self._client.get(
                url,
                params={"$format": "json", "$select": "НаименованиеПолное"},
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError):
            return None
        if resp.status_code != 200:
            return None
        payload = resp.json()
        name = payload.get("НаименованиеПолное")
        return str(name).strip() if name else None

    async def _get_realization(self, entity: str, guid: uuid.UUID) -> httpx.Response:
        url = f"/{entity}(guid'{guid}')"
        return await self._client.get(url, params={"$format": "json", "$select": "Number,Date"})

    async def fetch_related_realization(self, ref: RelatedRef) -> RealizationSummary | None:
        try:
            resp = await self._get_realization(ref.entity, ref.guid)
            if resp.status_code == 200:
                payload = resp.json()
                return RealizationSummary(
                    number=str(payload.get("Number", "")),
                    doc_date=parse_odata_date(payload.get("Date")),
                )
            log.warning("realization lookup %s returned %s", ref.guid, resp.status_code)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
            log.warning("realization lookup %s failed: %s", ref.guid, e)
        return None

    async def _get_transfer_receiver_name(self, entity: str, guid: uuid.UUID) -> str | None:
        url = f"/{entity}(guid'{guid}')/СкладПолучатель"
        params_variants = (
            {"$format": "json", "$select": "Description,Наименование,НаименованиеПолное"},
            {"$format": "json"},
        )
        for params in params_variants:
            try:
                resp = await self._client.get(url, params=params)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError):
                return None
            if resp.status_code != 200:
                continue
            payload = resp.json()
            for key in ("Description", "Наименование", "НаименованиеПолное"):
                value = payload.get(key)
                if value:
                    return str(value).strip()
        return None

    async def mark_document(
        self,
        doc_guid: uuid.UUID,
        doc_entity: str,
        property_key: uuid.UUID,
        value: datetime,
    ) -> None:
        url = "/InformationRegister_ДополнительныеСведения"
        formatted_value = value.strftime("%Y-%m-%dT%H:%M:%S")
        body = {
            "Объект": str(doc_guid),
            "Объект_Type": f"StandardODATA.{doc_entity}",
            "Свойство_Key": str(property_key),
            "Значение": formatted_value,
            "Значение_Type": "Edm.DateTime",
        }
        params = {"$format": "json"}
        resp = await self._client.post(url, json=body, params=params)
        if resp.status_code in (200, 201):
            return
        if resp.status_code == 400:
            try:
                data = resp.json()
            except ValueError:
                data = {}
            nested_error = data.get("odata.error") if isinstance(data, dict) else None
            nested_code = nested_error.get("code") if isinstance(nested_error, dict) else None
            err_code = data.get("code") if isinstance(data, dict) else None
            if str(err_code or nested_code) == "15":
                patch_url = (
                    f"{url}(Объект='{doc_guid}',"
                    f"Объект_Type='StandardODATA.{doc_entity}',"
                    f"Свойство_Key=guid'{property_key}')"
                )
                patch_body = {
                    "Значение": formatted_value,
                    "Значение_Type": "Edm.DateTime",
                }
                patch_resp = await self._client.patch(patch_url, json=patch_body, params=params)
                if patch_resp.status_code in (200, 204):
                    return
                raise OneCUnavailable(f"1С PATCH mark вернула {patch_resp.status_code}")
        raise OneCUnavailable(f"1С POST mark вернула {resp.status_code}")

    async def mark_document_boolean(
        self,
        doc_guid: uuid.UUID,
        doc_entity: str,
        property_key: uuid.UUID,
        value: bool,
    ) -> None:
        url = (
            "/InformationRegister_"
            "\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c"
            "\u043d\u044b\u0435\u0421\u0432\u0435\u0434\u0435\u043d\u0438\u044f"
        )
        body = {
            "\u041e\u0431\u044a\u0435\u043a\u0442": str(doc_guid),
            "\u041e\u0431\u044a\u0435\u043a\u0442_Type": f"StandardODATA.{doc_entity}",
            "\u0421\u0432\u043e\u0439\u0441\u0442\u0432\u043e_Key": str(property_key),
            "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435": value,
            "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435_Type": "Edm.Boolean",
        }
        params = {"$format": "json"}
        resp = await self._client.post(url, json=body, params=params)
        if resp.status_code in (200, 201):
            return
        if resp.status_code == 400:
            try:
                data = resp.json()
            except ValueError:
                data = {}
            nested_error = data.get("odata.error") if isinstance(data, dict) else None
            nested_code = nested_error.get("code") if isinstance(nested_error, dict) else None
            err_code = data.get("code") if isinstance(data, dict) else None
            if str(err_code or nested_code) == "15":
                patch_url = (
                    f"{url}(\u041e\u0431\u044a\u0435\u043a\u0442='{doc_guid}',"
                    f"\u041e\u0431\u044a\u0435\u043a\u0442_Type='StandardODATA.{doc_entity}',"
                    f"\u0421\u0432\u043e\u0439\u0441\u0442\u0432\u043e_Key=guid'{property_key}')"
                )
                patch_body = {
                    "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435": value,
                    "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435_Type": "Edm.Boolean",
                }
                patch_resp = await self._client.patch(patch_url, json=patch_body, params=params)
                if patch_resp.status_code in (200, 204):
                    return
                raise OneCUnavailable(f"1C PATCH boolean mark returned {patch_resp.status_code}")
        raise OneCUnavailable(f"1C POST boolean mark returned {resp.status_code}")

    async def fetch_invoices_page(
        self,
        *,
        date_from: date,
        date_to: date | None,
        skip: int,
        top: int,
        include_deleted: bool = False,
        server_date_filter: bool = True,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        if server_date_filter:
            filters.append(f"Date ge datetime'{date_from.isoformat()}T00:00:00'")
        if server_date_filter and date_to is not None:
            filters.append(f"Date le datetime'{date_to.isoformat()}T23:59:59'")
        if not include_deleted:
            filters.append("DeletionMark eq false")
        params = {
            "$format": "json",
            "$expand": INVOICE_SYNC_EXPAND,
            "$select": ",".join(INVOICE_SYNC_SELECT),
        }
        if filters:
            params["$filter"] = " and ".join(filters)
        params["$skip"] = str(skip)
        params["$top"] = str(top)
        try:
            resp = await self._client.get(
                f"/Document_СчетФактураВыданный?{_odata_query(params)}"
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
            raise OneCUnavailable("1С недоступна при синхронизации") from e
        if resp.status_code == 401:
            raise OneCUnavailable("Не удалось авторизоваться в 1С")
        if resp.status_code != 200:
            detail = resp.text[:500].replace("\r", " ").replace("\n", " ")
            raise OneCUnavailable(
                f"1С вернула {resp.status_code} при синхронизации: {detail}"
            )
        data = resp.json()
        return data.get("value", [])

    async def get_change_restriction_date(self) -> date | None:
        params = {
            "$format": "json",
            "$select": "ДатаЗапрета",
            "$orderby": "ДатаЗапрета desc",
            "$top": "1",
        }
        try:
            resp = await self._client.get(
                "/InformationRegister_ДатыЗапретаИзменения", params=params
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError):
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get("value", [])
        if not items:
            return None
        raw = items[0].get("ДатаЗапрета")
        return parse_odata_date(raw) if raw else None

    async def patch_storage_link(
        self,
        doc_guid: uuid.UUID,
        doc_entity: str,
        storage_link: str,
    ) -> None:
        url = f"/{doc_entity}(guid'{doc_guid}')"
        body = {"kzvСсылкаНаКопию": storage_link}
        params = {"$format": "json"}
        try:
            resp = await self._client.patch(url, json=body, params=params)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
            raise OneCUnavailable("1С недоступна при патче ссылки") from e
        if resp.status_code not in (200, 204):
            raise OneCUnavailable(f"1С вернула {resp.status_code} при patch storage link")
