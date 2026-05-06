import pytest

from app.config import get_settings
from app.services import system_settings as settings_svc
from app.services.operators import ensure_operator


@pytest.mark.asyncio
async def test_1c_timestamps_falls_back_to_env(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_1C_TIMESTAMPS", "false")
    get_settings.cache_clear()
    try:
        assert await settings_svc.is_1c_timestamps_enabled(db_session) is False
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_1c_timestamps_db_value_overrides_env(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_1C_TIMESTAMPS", "false")
    get_settings.cache_clear()
    try:
        await settings_svc.set_1c_timestamps_enabled(db_session, True)
        await db_session.commit()
        assert await settings_svc.is_1c_timestamps_enabled(db_session) is True
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_can_toggle_1c_timestamps_from_ui(client, db_session):
    await ensure_operator(db_session, "Admin", bootstrap=True)
    await db_session.commit()
    client.cookies.set("operator_name", "Admin")

    r = await client.patch("/ui/admin/settings/1c-timestamps", data={"enabled": "false"})

    assert r.status_code == 200
    assert "Выключены для всех клиентов" in r.text
    assert await settings_svc.is_1c_timestamps_enabled(db_session) is False
