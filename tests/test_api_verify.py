import uuid as _u
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest

from app.services.odata import NormalizedDocument


def _bc(g): return str(int.from_bytes(_u.UUID(g).bytes, "big"))


def _norm():
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров", doc_kind="ПРМ",
        doc_number="X", doc_date=_date(2026, 4, 20),
        related_realization_ref=None, raw_payload={"Number": "X", "Date": "2026-04-20T00:00:00"},
    )


@pytest.fixture
def stub_one_c():
    from app.deps import get_one_c_client
    from app.main import app
    mock = AsyncMock()
    mock.lookup_document_with_related.return_value = _norm()
    app.dependency_overrides[get_one_c_client] = lambda: mock
    yield mock


async def _seal_envelope(client, doc_guids):
    client.cookies.set("operator_name", "Ivan")
    env = (await client.post("/api/envelopes", json={})).json()
    for g in doc_guids:
        await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": _bc(g)})
    b1 = (await client.post("/api/branches", json={"name": "A"})).json()
    b2 = (await client.post("/api/branches", json={"name": "B"})).json()
    s1 = (await client.post("/api/signers", json={"last_name": "X", "first_name": "x"})).json()
    s2 = (await client.post("/api/signers", json={"last_name": "Y", "first_name": "y"})).json()
    await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"], "notes": None,
    })
    return env


@pytest.mark.asyncio
async def test_verify_full_flow_no_discrepancy(client, stub_one_c):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _seal_envelope(client, [g])
    r = await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    assert r.status_code == 200
    r = await client.post(f"/api/envelopes/{env['id']}/verify/scan", json={"barcode": _bc(g)})
    assert r.status_code == 200
    assert r.json()["matched"] is True
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": False})
    assert r.status_code == 200
    assert r.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_verify_unknown_barcode_returns_not_in_envelope(client, stub_one_c):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _seal_envelope(client, [g])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/scan", json={"barcode": "0"})
    assert r.json()["matched"] is False
    assert r.json()["reason"] == "not_in_envelope"


@pytest.mark.asyncio
async def test_verify_finish_without_force_409(client, stub_one_c):
    env = await _seal_envelope(client, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": False})
    assert r.status_code == 409
    assert r.json()["code"] == "verification_unscanned"


@pytest.mark.asyncio
async def test_verify_finish_force_returns_discrepancy(client, stub_one_c):
    env = await _seal_envelope(client, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": True})
    assert r.status_code == 200
    assert r.json()["status"] == "verified_with_discrepancy"
    assert len(r.json()["missing_docs"]) == 2
