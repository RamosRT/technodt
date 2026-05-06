from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import AuditLog, Envelope
from app.parsing import optional_query_date
from app.schemas.audit import AuditOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def get_audit(
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    event: str | None = None,
    actor: str | None = None,
    envelope: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    stmt = select(AuditLog).outerjoin(Envelope, AuditLog.envelope_id == Envelope.id)
    if date_from:
        stmt = stmt.where(AuditLog.at >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to:
        stmt = stmt.where(AuditLog.at <= datetime.combine(date_to, time.max, tzinfo=UTC))
    if event:
        stmt = stmt.where(AuditLog.event == event)
    if actor:
        stmt = stmt.where(AuditLog.actor.ilike(f"%{actor.strip()}%"))
    if envelope:
        term = f"%{envelope.strip()}%"
        stmt = stmt.where(or_(Envelope.number.ilike(term), Envelope.barcode.ilike(term)))

    total = (await session.execute(stmt.with_only_columns(func.count(AuditLog.id)).order_by(None))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(AuditLog.at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [AuditOut.model_validate(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
