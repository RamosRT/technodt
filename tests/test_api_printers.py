import json

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_printer_list_requires_auth(client):
    r = await client.get("/api/printers")

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_printer_list_returns_configured_printers(client, monkeypatch):
    monkeypatch.setenv(
        "PRINTERS_JSON",
        json.dumps(
            [
                {
                    "id": "zpl-main",
                    "name": "Zebra склад",
                    "kind": "zpl",
                    "host": "192.168.1.50",
                    "port": 9100,
                    "dpi": 200,
                }
            ]
        ),
    )
    get_settings.cache_clear()
    client.cookies.set("operator_name", "Test")

    r = await client.get("/api/printers")

    assert r.status_code == 200
    assert r.json()["items"][0]["id"] == "zpl-main"


@pytest.mark.asyncio
async def test_printer_list_rejects_malformed_config(client, monkeypatch):
    monkeypatch.setenv("PRINTERS_JSON", "{bad")
    get_settings.cache_clear()
    client.cookies.set("operator_name", "Test")

    r = await client.get("/api/printers")

    assert r.status_code == 500
    assert r.json()["code"] == "printer_config_invalid"


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
async def test_label_send_calls_zpl_sender(client, monkeypatch):
    monkeypatch.setenv(
        "PRINTERS_JSON",
        json.dumps(
            [
                {
                    "id": "zpl-main",
                    "name": "Zebra склад",
                    "kind": "zpl",
                    "host": "127.0.0.1",
                    "port": 9100,
                    "dpi": 200,
                }
            ]
        ),
    )
    get_settings.cache_clear()
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
async def test_inventory_send_returns_501(client, monkeypatch):
    monkeypatch.setenv(
        "PRINTERS_JSON",
        json.dumps([{"id": "a4-main", "name": "A4", "kind": "a4"}]),
    )
    get_settings.cache_clear()
    client.cookies.set("operator_name", "Test")
    created = await client.post("/api/envelopes")

    r = await client.post(
        f"/api/envelopes/{created.json()['id']}/print/inventory/send",
        params={"printer_id": "a4-main"},
    )

    assert r.status_code == 501
    assert r.json()["code"] == "inventory_print_not_implemented"
