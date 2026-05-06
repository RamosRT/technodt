from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_session
from app.main import app


def _test_db_url() -> str:
    s = get_settings()
    return s.database_url_test or s.database_url


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        _test_db_url(), pool_pre_ping=True, connect_args={"ssl": False}
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def truncate_tables(test_engine):
    """Wipe all data between tests; schema stays."""
    async with test_engine.begin() as conn:
        for tbl in (
            "onec_mark_logs",
            "audit_log",
            "envelope_documents",
            "envelopes",
            "signers",
            "branches",
            "operators",
            "printers",
            "system_settings",
        ):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_session():
        async with factory() as s:
            yield s

    from app.deps import get_one_c_client
    from app.services.odata import OneCClient
    stub = OneCClient(base_url="http://1c.example/odata/standard.odata", user="u", password="p", timeout=5)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_one_c_client] = lambda: stub

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await stub.aclose()


@pytest.fixture
def admin_token(monkeypatch):
    token = "test-admin-token-12345"
    monkeypatch.setenv("ADMIN_TOKEN", token)
    get_settings.cache_clear()
    yield token
    get_settings.cache_clear()
