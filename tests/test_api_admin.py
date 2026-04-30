import pytest

from app.services.operators import ensure_operator


async def _make_admin(db_session, client, username: str = "Admin"):
    await ensure_operator(db_session, username, bootstrap=True)
    await db_session.commit()
    client.cookies.set("operator_name", username)


@pytest.mark.asyncio
async def test_admin_reset_requires_token(client):
    r = await client.post("/api/admin/reset", json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_reset_requires_confirm(client, db_session):
    await _make_admin(db_session, client)
    r = await client.post("/api/admin/reset", json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_reset_truncates_envelopes(client, db_session):
    await _make_admin(db_session, client)
    client.cookies.set("operator_name", "Ivan")
    created = (await client.post("/api/envelopes", json={})).json()
    env_id = created["id"]

    assert (await client.get(f"/api/envelopes/{env_id}")).status_code == 200

    client.cookies.set("operator_name", "Admin")
    r = await client.post(
        "/api/admin/reset",
        json={"confirm": "I_KNOW_WHAT_I_DO"},
    )
    assert r.status_code == 200

    assert (await client.get(f"/api/envelopes/{env_id}")).status_code == 404


@pytest.mark.asyncio
async def test_admin_reset_404_in_production(client, db_session, monkeypatch):
    await _make_admin(db_session, client)
    monkeypatch.setenv("ENV", "production")
    from app.config import get_settings
    get_settings.cache_clear()
    r = await client.post("/api/admin/reset",
                           json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 404
