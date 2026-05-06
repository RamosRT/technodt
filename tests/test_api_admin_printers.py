import pytest

from app.models import Printer
from app.services.operators import ensure_operator


async def _make_admin(db_session, client, username: str = "Admin"):
    await ensure_operator(db_session, username, bootstrap=True)
    await db_session.commit()
    client.cookies.set("operator_name", username)


@pytest.mark.asyncio
async def test_admin_printers_require_admin(client):
    r = await client.get("/api/admin/printers")

    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_can_create_list_patch_and_delete_printer(client, db_session):
    await _make_admin(db_session, client)

    created = await client.post(
        "/api/admin/printers",
        json={
            "id": "a4-main",
            "name": "A4 бухгалтерия",
            "kind": "a4",
            "share_name": "HP-Laser",
        },
    )
    assert created.status_code == 201
    assert created.json()["share_name"] == "HP-Laser"

    listed = await client.get("/api/admin/printers")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == "a4-main"

    patched = await client.patch("/api/admin/printers/a4-main", json={"is_active": False})
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    deleted = await client.delete("/api/admin/printers/a4-main")
    assert deleted.status_code == 204

    listed = await client.get("/api/admin/printers")
    assert listed.json()["items"] == []


@pytest.mark.asyncio
async def test_admin_printer_create_rejects_duplicate(client, db_session):
    await _make_admin(db_session, client)
    db_session.add(Printer(id="zpl-main", name="ZPL", kind="zpl", host="127.0.0.1", port=9100))
    await db_session.commit()

    r = await client.post(
        "/api/admin/printers",
        json={
            "id": "zpl-main",
            "name": "Other",
            "kind": "zpl",
            "host": "127.0.0.2",
            "port": 9100,
        },
    )

    assert r.status_code == 409
    assert r.json()["code"] == "printer_exists"
