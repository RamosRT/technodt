import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def write_event(
    session: AsyncSession,
    *,
    envelope_id: uuid.UUID | None,
    event: str,
    actor: str = "system",
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(envelope_id=envelope_id, event=event, actor=actor, payload=payload or {})
    session.add(row)
    await session.flush()
    return row
