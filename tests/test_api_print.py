"""API integration tests for print endpoints.

WeasyPrint is mocked via patch('app.services.printing._html_to_pdf') so the
test suite runs without system-level WeasyPrint dependencies.
python-barcode is mocked via patch('app.services.printing.generate_barcode_svg').
"""
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.odata import NormalizedDocument

# ── helpers ───────────────────────────────────────────────────────────────────

FAKE_PDF = b"%PDF-1.4 fake"
FAKE_SVG = "<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"


def _norm():
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="ПРМ",
        doc_number="ПЕР-1",
        doc_date=date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-1", "Date": "2026-04-20T00:00:00"},
    )


@pytest.fixture
def stub_one_c():
    from app.deps import get_one_c_client
    from app.main import app
    mock = AsyncMock()
    mock.lookup_document_with_related.return_value = _norm()
    app.dependency_overrides[get_one_c_client] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_one_c_client, None)


async def _sealed_envelope(client):
    """Create an envelope with one document, seal it; return its JSON."""
    client.cookies.set("operator_name", "Tester")
    b1 = (await client.post("/api/branches", json={"name": "Отправитель"})).json()
    b2 = (await client.post("/api/branches", json={"name": "Получатель"})).json()
    s1 = (await client.post("/api/signers", json={"last_name": "Иванов", "first_name": "И"})).json()
    s2 = (await client.post("/api/signers", json={"last_name": "Петров", "first_name": "П"})).json()

    env = (await client.post("/api/envelopes", json={})).json()
    barcode = "00000000000000000000000000000001"
    # barcode that decodes to a valid UUID
    import uuid as _u
    guid = str(_u.UUID(bytes=int(barcode).to_bytes(16, "big")))
    barcode = str(int.from_bytes(_u.UUID(guid).bytes, "big"))
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": barcode})

    seal_payload = {
        "signer_sender_id": s1["id"],
        "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"],
        "destination_branch_id": b2["id"],
    }
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json=seal_payload)
    assert r.status_code == 200, r.text
    return r.json()


# ── inventory PDF ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_print_inventory_returns_pdf(client, stub_one_c):
    env = await _sealed_envelope(client)
    with (
        patch("app.services.printing._html_to_pdf", return_value=FAKE_PDF),
        patch("app.services.printing.generate_barcode_svg", return_value=FAKE_SVG),
    ):
        r = await client.get(f"/api/envelopes/{env['id']}/print/inventory")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == FAKE_PDF


@pytest.mark.asyncio
async def test_print_inventory_filename_contains_envelope_number(client, stub_one_c):
    env = await _sealed_envelope(client)
    with (
        patch("app.services.printing._html_to_pdf", return_value=FAKE_PDF),
        patch("app.services.printing.generate_barcode_svg", return_value=FAKE_SVG),
    ):
        r = await client.get(f"/api/envelopes/{env['id']}/print/inventory")
    disposition = r.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert env["number"].replace("ТА-", "TA-") in disposition or env["number"] in disposition


@pytest.mark.asyncio
async def test_print_inventory_404_for_nonexistent_envelope(client):
    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/envelopes/{fake_id}/print/inventory")
    assert r.status_code == 404


# ── label PDF ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_print_label_pdf_returns_pdf(client, stub_one_c):
    env = await _sealed_envelope(client)
    with (
        patch("app.services.printing._html_to_pdf", return_value=FAKE_PDF),
        patch("app.services.printing.generate_barcode_svg", return_value=FAKE_SVG),
    ):
        r = await client.get(f"/api/envelopes/{env['id']}/print/label")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_print_label_pdf_404_for_nonexistent_envelope(client):
    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/envelopes/{fake_id}/print/label")
    assert r.status_code == 404


# ── label ZPL ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_print_label_zpl_returns_zpl(client, stub_one_c):
    env = await _sealed_envelope(client)
    r = await client.get(f"/api/envelopes/{env['id']}/print/label?format=zpl")
    assert r.status_code == 200
    assert "octet-stream" in r.headers["content-type"]
    assert b"^XA" in r.content
    assert b"^XZ" in r.content


@pytest.mark.asyncio
async def test_print_label_zpl_300dpi_uses_correct_dimensions(client, stub_one_c):
    env = await _sealed_envelope(client)
    r = await client.get(f"/api/envelopes/{env['id']}/print/label?format=zpl&dpi=300")
    assert r.status_code == 200
    assert b"^PW1181" in r.content
    assert b"^LL591" in r.content


@pytest.mark.asyncio
async def test_print_label_zpl_404_for_nonexistent_envelope(client):
    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/envelopes/{fake_id}/print/label?format=zpl")
    assert r.status_code == 404
