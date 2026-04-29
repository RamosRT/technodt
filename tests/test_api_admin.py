import pytest


@pytest.mark.asyncio
async def test_admin_reset_requires_token(client):
    r = await client.post("/api/admin/reset", json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_reset_requires_confirm(client, admin_token):
    r = await client.post("/api/admin/reset",
                           headers={"X-Admin-Token": admin_token}, json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_reset_truncates_envelopes(client, admin_token):
    client.cookies.set("operator_name", "Ivan")
    created = (await client.post("/api/envelopes", json={})).json()
    env_id = created["id"]

    assert (await client.get(f"/api/envelopes/{env_id}")).status_code == 200

    r = await client.post(
        "/api/admin/reset",
        headers={"X-Admin-Token": admin_token},
        json={"confirm": "I_KNOW_WHAT_I_DO"},
    )
    assert r.status_code == 200

    assert (await client.get(f"/api/envelopes/{env_id}")).status_code == 404


@pytest.mark.asyncio
async def test_admin_reset_404_in_production(client, admin_token, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    from app.config import get_settings
    get_settings.cache_clear()
    r = await client.post("/api/admin/reset",
                           headers={"X-Admin-Token": admin_token},
                           json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 404
