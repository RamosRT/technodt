import json
import uuid
from pathlib import Path

import httpx
import pytest
import respx

from app.exceptions import DocumentNotInOneC, OneCUnavailable
from app.services.odata import KNOWN_DOC_TYPES, OneCClient, SELECT_FIELDS

FIXTURES = Path(__file__).parent / "fixtures" / "odata"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def base_url():
    return "http://1c.example/odata/standard.odata"


@pytest.fixture
def odata_client(base_url):
    return OneCClient(base_url=base_url, user="u", password="p", timeout=5)


@pytest.mark.asyncio
async def test_known_doc_types_are_two():
    assert KNOWN_DOC_TYPES == ("Document_ПеремещениеТоваров", "Document_СчетФактураВыданный")
    assert "Document_ПеремещениеТоваров" in SELECT_FIELDS


@pytest.mark.asyncio
async def test_fetch_document_returns_peremeshchenie_on_first_try(odata_client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(200, json=_load("peremeshchenie.json"))
        entity, payload = await odata_client.fetch_document(guid)
    assert entity == "Document_ПеремещениеТоваров"
    assert payload["Number"] == "ПЕР-000123"


@pytest.mark.asyncio
async def test_fetch_document_falls_through_to_second_type(odata_client, base_url):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        entity, payload = await odata_client.fetch_document(guid)
    assert entity == "Document_СчетФактураВыданный"


@pytest.mark.asyncio
async def test_fetch_document_all_404_raises_not_found(odata_client, base_url):
    guid = uuid.UUID("99999999-9999-9999-9999-999999999999")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(404)
        with pytest.raises(DocumentNotInOneC):
            await odata_client.fetch_document(guid)


@pytest.mark.asyncio
async def test_fetch_document_401_raises_unavailable(odata_client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(401)
        with pytest.raises(OneCUnavailable):
            await odata_client.fetch_document(guid)


@pytest.mark.asyncio
async def test_fetch_document_network_error_raises_unavailable(odata_client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").mock(side_effect=httpx.ConnectError("boom"))
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(OneCUnavailable):
            await odata_client.fetch_document(guid)
