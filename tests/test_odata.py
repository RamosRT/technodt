import json
import uuid
from datetime import date as _date
from pathlib import Path

import httpx
import pytest
import respx

from app.exceptions import DocumentNotInOneC, OneCUnavailable
from app.services.odata import KNOWN_DOC_TYPES, OneCClient, SELECT_FIELDS, normalize_document

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


# Task 12 tests
def test_normalize_peremeshchenie():
    payload = _load("peremeshchenie.json")
    n = normalize_document("Document_ПеремещениеТоваров", payload)
    assert n.doc_kind == "Перемещение товаров"
    assert n.doc_number == "ПЕР-000123"
    assert n.doc_date == _date(2026, 4, 20)
    assert n.related_realization_ref is None


def test_normalize_upd_with_related():
    payload = _load("sf_upd.json")
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.doc_kind == "УПД"
    assert n.doc_number == "СФВ-000456"
    assert n.related_realization_ref is not None
    assert str(n.related_realization_ref.guid) == "33333333-3333-3333-3333-333333333333"
    assert n.related_realization_ref.entity == "Document_РеализацияТоваровУслуг"


def test_normalize_ukd():
    payload = _load("sf_ukd.json")
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.doc_kind == "УКД"


def test_normalize_sf_without_related_returns_none():
    payload = {"Number": "X", "Date": "2026-04-22T00:00:00", "Корректировочный": False}
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.related_realization_ref is None


@pytest.mark.asyncio
async def test_lookup_with_related_fills_related_fields(odata_client, base_url):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        mock.get(
            "/Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')"
        ).respond(200, json=_load("realizatsiya.json"))
        result = await odata_client.lookup_document_with_related(guid)
    assert result.doc_kind == "УПД"
    assert result.related_realization_number == "РЕА-000999"
    assert result.related_realization_date == _date(2026, 4, 19)


@pytest.mark.asyncio
async def test_lookup_with_related_swallows_realization_error(odata_client, base_url, caplog):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        mock.get(
            "/Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')"
        ).mock(side_effect=httpx.ConnectError("boom"))
        result = await odata_client.lookup_document_with_related(guid)
    assert result.related_realization_number is None
    assert result.related_realization_date is None
