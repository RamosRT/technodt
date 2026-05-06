from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import SystemSetting

ENABLE_1C_TIMESTAMPS = "enable_1c_timestamps"


async def get_bool_setting(session: AsyncSession, key: str, *, default: bool) -> bool:
    row = (
        await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalar_one_or_none()
    if row is None:
        return default
    return bool(row.value.get("enabled", default))


async def set_bool_setting(session: AsyncSession, key: str, enabled: bool) -> SystemSetting:
    row = (
        await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value={"enabled": enabled})
        session.add(row)
    else:
        row.value = {"enabled": enabled}
    await session.flush()
    return row


async def is_1c_timestamps_enabled(session: AsyncSession) -> bool:
    return await get_bool_setting(
        session,
        ENABLE_1C_TIMESTAMPS,
        default=get_settings().enable_1c_timestamps,
    )


async def set_1c_timestamps_enabled(session: AsyncSession, enabled: bool) -> SystemSetting:
    return await set_bool_setting(session, ENABLE_1C_TIMESTAMPS, enabled)
