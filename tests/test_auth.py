import pytest
from fastapi import APIRouter

from app.auth import require_admin, require_operator
from app.main import app
from app.services.operators import ensure_operator


@pytest.fixture(autouse=True)
def _add_probe_routes():
    router = APIRouter()

    @router.get("/_probe/operator")
    async def probe_operator(name: str = require_operator()):  # noqa: B008
        return {"operator": name}

    @router.get("/_probe/admin")
    async def probe_admin(_=require_admin()):  # noqa: B008
        return {"ok": True}

    app.include_router(router)
    yield
    app.routes[:] = [r for r in app.routes if not getattr(r, "path", "").startswith("/_probe")]


@pytest.mark.asyncio
async def test_operator_required_returns_401_without_cookie(client):
    r = await client.get("/_probe/operator")
    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_operator_required_returns_name_with_cookie(client):
    # Set cookie directly on client instance
    client.cookies.set("operator_name", "Ivan")
    r = await client.get("/_probe/operator")
    assert r.status_code == 200
    assert r.json() == {"operator": "Ivan"}


@pytest.mark.asyncio
async def test_admin_required_returns_401_without_header(client, admin_token):
    r = await client.get("/_probe/admin")
    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_required_passes_with_admin_cookie(client, db_session):
    await ensure_operator(db_session, "Admin", bootstrap=True)
    await db_session.commit()
    client.cookies.set("operator_name", "Admin")
    r = await client.get("/_probe/admin")
    assert r.status_code == 200
