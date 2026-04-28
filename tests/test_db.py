import pytest
from sqlalchemy import text

from app.db import get_engine, get_session_factory


@pytest.mark.asyncio
async def test_can_open_session_and_select_one(monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "database_url", s.database_url_test or s.database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
