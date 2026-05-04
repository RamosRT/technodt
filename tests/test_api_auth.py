import pytest

from app.services.operators import ensure_operator


@pytest.mark.asyncio
async def test_login_sets_cookie(client):
    r = await client.post("/api/auth/login", json={"name": "Иванов"})

    assert r.status_code == 200
    assert r.json() == {"ok": True, "operator": "Иванов"}
    assert "operator_name" in client.cookies


@pytest.mark.asyncio
async def test_me_returns_operator_with_valid_cookie(client):
    await client.post("/api/auth/login", json={"name": "Петров"})

    r = await client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json() == {"operator": "Петров", "is_admin": False}


@pytest.mark.asyncio
async def test_me_returns_401_without_cookie(client):
    r = await client.get("/api/auth/me")

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_inactive_operator_cannot_login(client, db_session):
    op = await ensure_operator(db_session, "Сидоров")
    op.is_active = False
    await db_session.commit()

    r = await client.post("/api/auth/login", json={"name": "Сидоров"})

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_login_reports_bootstrap_admin(client, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN", "Главный")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        await client.post("/api/auth/login", json={"name": "Главный"})
        r = await client.get("/api/auth/me")
    finally:
        get_settings.cache_clear()

    assert r.status_code == 200
    assert r.json() == {"operator": "Главный", "is_admin": True}


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    await client.post("/api/auth/login", json={"name": "Иванов"})

    r = await client.post("/api/auth/logout")

    assert r.status_code == 204
    assert "operator_name" not in client.cookies
