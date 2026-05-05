import uuid as _u
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest
from app.services.odata import NormalizedDocument


def _bc(g: str) -> str:
    return str(int.from_bytes(_u.UUID(g).bytes, "big"))


def _norm():
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-1",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-1", "Date": "2026-04-20T00:00:00"},
    )


@pytest.fixture
def stub_one_c():
    """Replaces the OneCClient on app.dependency_overrides with an AsyncMock."""
    from app.main import app
    from app.deps import get_one_c_client
    mock = AsyncMock()
    mock.lookup_document_with_related.return_value = _norm()
    app.dependency_overrides[get_one_c_client] = lambda: mock
    yield mock


@pytest.mark.asyncio
async def test_post_envelope_requires_operator_cookie(client):
    r = await client.post("/api/envelopes", json={})
    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_post_envelope_creates_draft(client):
    client.cookies.set("operator_name", "Ivan")
    r = await client.post("/api/envelopes", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["created_by"] == "Ivan"
    assert body["number"].startswith("ТА-")
    assert body["barcode"].isdigit() and len(body["barcode"]) == 16


@pytest.mark.asyncio
async def test_get_envelope_by_id_returns_object(client):
    client.cookies.set("operator_name", "Ivan")
    created = (await client.post("/api/envelopes", json={})).json()
    r = await client.get(f"/api/envelopes/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_envelope_by_id_404(client):
    r = await client.get("/api/envelopes/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["code"] == "envelope_not_found"


@pytest.mark.asyncio
async def test_get_envelope_by_barcode(client):
    client.cookies.set("operator_name", "Ivan")
    created = (await client.post("/api/envelopes", json={})).json()
    r = await client.get(f"/api/envelopes/by-barcode/{created['barcode']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_envelope_by_barcode_404(client):
    r = await client.get("/api/envelopes/by-barcode/0000000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_recent_envelopes_returns_current_operator_activity(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env1 = (await client.post("/api/envelopes", json={})).json()
    doc = (await client.post(
        f"/api/envelopes/{env1['id']}/documents",
        json={"barcode": _bc("11111111-1111-1111-1111-111111111111")},
    )).json()
    env2 = (await client.post("/api/envelopes", json={})).json()

    client.cookies.set("operator_name", "Olga")
    await client.post("/api/envelopes", json={})

    client.cookies.set("operator_name", "Ivan")
    b1, b2, s1, s2 = await _make_dictionary_via_api(client)
    await client.post(f"/api/envelopes/{env1['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"],
        "notes": None,
    })
    await client.post(f"/api/envelopes/{env1['id']}/verify/start", json={})
    await client.post(f"/api/envelopes/{env1['id']}/verify/scan", json={"barcode": doc["doc_barcode"]})
    await client.post(f"/api/envelopes/{env1['id']}/verify/finish", json={"force": False})

    r = await client.get("/api/envelopes/recent")
    assert r.status_code == 200
    items = r.json()
    assert [item["id"] for item in items] == [env2["id"]]
    assert all(item["created_by"] == "Ivan" for item in items)


@pytest.mark.asyncio
async def test_post_document_adds_doc(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    assert r.status_code == 201
    body = r.json()
    assert body["doc_kind"] == "Перемещение товаров"
    assert body["doc_barcode"] == bc


@pytest.mark.asyncio
async def test_post_document_invalid_barcode(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": "abc"})
    assert r.status_code == 400
    assert r.json()["code"] == "barcode_invalid"


@pytest.mark.asyncio
async def test_post_document_duplicate(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    assert r.status_code == 409
    assert r.json()["code"] == "document_already_in_envelope"


@pytest.mark.asyncio
async def test_delete_document(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    doc = (await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})).json()
    r = await client.delete(f"/api/envelopes/{env['id']}/documents/{doc['id']}")
    assert r.status_code == 204


async def _make_dictionary_via_api(client):
    b1 = (await client.post("/api/branches", json={"name": "A"})).json()
    b2 = (await client.post("/api/branches", json={"name": "B"})).json()
    s1 = (await client.post("/api/signers", json={"last_name": "X", "first_name": "x"})).json()
    s2 = (await client.post("/api/signers", json={"last_name": "Y", "first_name": "y"})).json()
    return b1, b2, s1, s2


@pytest.mark.asyncio
async def test_seal_happy(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    b1, b2, s1, s2 = await _make_dictionary_via_api(client)
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"],
        "notes": None,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "sealed"


@pytest.mark.asyncio
async def test_seal_empty_envelope_invalid(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    b1, b2, s1, s2 = await _make_dictionary_via_api(client)
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"],
        "notes": None,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_seal_payload"


@pytest.mark.asyncio
async def test_seal_route_returns_400_when_unknown_signer(client, stub_one_c):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    fake = "00000000-0000-0000-0000-000000000001"
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": fake, "signer_receiver_id": fake,
        "origin_branch_id": fake, "destination_branch_id": fake,
        "notes": None,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_seal_payload"
