import logging
import uuid
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
