import pytest

from app.models import Printer


@pytest.mark.asyncio
async def test_printer_list_requires_auth(client):
    r = await client.get("/api/printers")

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_printer_list_returns_active_db_printers(client, db_session):
    db_session.add_all(
        [
            Printer(id="zpl-main", name="Zebra склад", kind="zpl", host="127.0.0.1", port=9100, dpi=200),
            Printer(id="old", name="Old", kind="zpl", host="127.0.0.2", port=9100, is_active=False),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", "Test")

    r = await client.get("/api/printers")

    assert r.status_code == 200
    assert [item["id"] for item in r.json()["items"]] == ["zpl-main"]


@pytest.mark.asyncio
async def test_label_send_unknown_printer_returns_404(client):
    client.cookies.set("operator_name", "Test")
    created = await client.post("/api/envelopes")

    r = await client.post(
        f"/api/envelopes/{created.json()['id']}/print/label/send",
        params={"printer_id": "missing"},
    )

    assert r.status_code == 404
    assert r.json()["code"] == "printer_not_found"


@pytest.mark.asyncio
async def test_label_send_calls_zpl_sender(client, db_session, monkeypatch):
    db_session.add(
        Printer(id="zpl-main", name="Zebra склад", kind="zpl", host="127.0.0.1", port=9100, dpi=200)
    )
    await db_session.commit()
    calls = []

    def fake_send(printer, payload):
        calls.append((printer.id, payload))

    monkeypatch.setattr("app.services.printers.send_zpl", fake_send)
    client.cookies.set("operator_name", "Test")
    created = await client.post("/api/envelopes")

    r = await client.post(
        f"/api/envelopes/{created.json()['id']}/print/label/send",
        params={"printer_id": "zpl-main"},
    )

    assert r.status_code == 204
    assert calls
    assert calls[0][0] == "zpl-main"
    assert "^XA" in calls[0][1]


@pytest.mark.asyncio
async def test_inventory_send_calls_a4_sender(client, db_session, monkeypatch):
    db_session.add(Printer(id="a4-main", name="A4", kind="a4", share_name="HP-Laser"))
    await db_session.commit()
    calls = []

    async def fake_send(session, envelope_id, printer):
        calls.append((envelope_id, printer.id))

    monkeypatch.setattr("app.services.printing.send_inventory_to_a4_printer", fake_send)
    client.cookies.set("operator_name", "Test")
    created = await client.post("/api/envelopes")

    r = await client.post(
        f"/api/envelopes/{created.json()['id']}/print/inventory/send",
        params={"printer_id": "a4-main"},
    )

    assert r.status_code == 204
    assert calls[0][1] == "a4-main"


@pytest.mark.asyncio
async def test_inventory_send_rejects_zpl_printer(client, db_session):
    db_session.add(Printer(id="zpl-main", name="ZPL", kind="zpl", host="127.0.0.1", port=9100))
    await db_session.commit()
    client.cookies.set("operator_name", "Test")
    created = await client.post("/api/envelopes")

    r = await client.post(
        f"/api/envelopes/{created.json()['id']}/print/inventory/send",
        params={"printer_id": "zpl-main"},
    )

    assert r.status_code == 400
    assert r.json()["code"] == "printer_not_a4"
