import pytest

from app.models import Branch, Printer, Signer


@pytest.mark.asyncio
async def test_operator_can_patch_workspace_settings(client, db_session):
    branch = Branch(name="Москва")
    signer = Signer(last_name="Иванов", first_name="Иван")
    db_session.add_all(
        [
            branch,
            signer,
            Printer(id="zpl-main", name="ZPL", kind="zpl", host="127.0.0.1", port=9100),
            Printer(id="a4-main", name="A4", kind="a4", share_name="HP-Laser"),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", "Test")

    r = await client.patch(
        "/api/operators/me/settings",
        json={
            "zpl_printer_id": "zpl-main",
            "a4_printer_id": "a4-main",
            "default_branch_id": str(branch.id),
            "default_signer_sender_id": str(signer.id),
        },
    )

    assert r.status_code == 200
    data = r.json()
    assert data["assigned_zpl_printer_id"] == "zpl-main"
    assert data["assigned_a4_printer_id"] == "a4-main"
    assert data["default_branch_id"] == str(branch.id)
    assert data["default_signer_sender_id"] == str(signer.id)


@pytest.mark.asyncio
async def test_operator_settings_null_clears_value(client, db_session):
    client.cookies.set("operator_name", "Test")
    await client.patch("/api/operators/me/settings", json={"zpl_printer_id": "zpl-main"})

    r = await client.patch("/api/operators/me/settings", json={"zpl_printer_id": None})

    assert r.status_code == 200
    assert r.json()["assigned_zpl_printer_id"] is None
