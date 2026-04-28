import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from app.exceptions import DocumentNotInOneC, OneCUnavailable

log = logging.getLogger(__name__)

SELECT_FIELDS: dict[str, tuple[str, ...]] = {
    "Document_ПеремещениеТоваров": ("Number", "Date"),
    "Document_СчетФактураВыданный": (
        "Number",
        "Date",
        "Корректировочный",
        "ДокументОснование",
        "ДокументОснование_Key",
        "ДокументОснование_Type",
    ),
}

KNOWN_DOC_TYPES: tuple[str, ...] = (
    "Document_ПеремещениеТоваров",
    "Document_СчетФактураВыданный",
)


@dataclass(frozen=True)
class RelatedRef:
    guid: uuid.UUID
    entity: str


@dataclass
class NormalizedDocument:
    entity: str
    doc_kind: str
    doc_number: str
    doc_date: date
    related_realization_ref: RelatedRef | None
    raw_payload: dict[str, Any]
    related_realization_number: str | None = None
    related_realization_date: date | None = None


def _parse_odata_date(s: str | None) -> date:
    if not s:
        raise ValueError("missing Date")
    return datetime.fromisoformat(s).date()


def _extract_related_ref(payload: dict[str, Any]) -> RelatedRef | None:
    raw_type = payload.get("ДокументОснование_Type")
    raw_key = payload.get("ДокументОснование_Key")
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


def normalize_document(entity: str, payload: dict[str, Any]) -> NormalizedDocument:
    if entity == "Document_ПеремещениеТоваров":
        kind = "Перемещение товаров"
        related = None
    elif entity == "Document_СчетФактураВыданный":
        kind = "УКД" if payload.get("Корректировочный") else "УПД"
        related = _extract_related_ref(payload)
    else:
        raise ValueError(f"unknown entity {entity}")
    return NormalizedDocument(
        entity=entity,
        doc_kind=kind,
        doc_number=str(payload.get("Number", "")),
        doc_date=_parse_odata_date(payload.get("Date")),
        related_realization_ref=related,
        raw_payload=payload,
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
        fields = ",".join(SELECT_FIELDS[entity])
        url = f"/{entity}(guid'{guid}')"
        return await self._client.get(url, params={"$format": "json", "$select": fields})

    async def lookup_document_with_related(self, guid: uuid.UUID) -> NormalizedDocument:
        entity, payload = await self.fetch_document(guid)
        normalized = normalize_document(entity, payload)
        if normalized.related_realization_ref is not None:
            ref = normalized.related_realization_ref
            try:
                resp = await self._get_realization(ref.entity, ref.guid)
                if resp.status_code == 200:
                    rp = resp.json()
                    normalized.related_realization_number = str(rp.get("Number", ""))
                    normalized.related_realization_date = _parse_odata_date(rp.get("Date"))
                else:
                    log.warning("realization lookup %s returned %s", ref.guid, resp.status_code)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
                log.warning("realization lookup %s failed: %s", ref.guid, e)
        return normalized

    async def _get_realization(self, entity: str, guid: uuid.UUID) -> httpx.Response:
        url = f"/{entity}(guid'{guid}')"
        return await self._client.get(url, params={"$format": "json", "$select": "Number,Date"})
