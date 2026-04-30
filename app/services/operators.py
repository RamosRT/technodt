import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operator


async def ensure_operator(
    session: AsyncSession,
    username: str,
    *,
    bootstrap: bool = False,
) -> Operator:
    username = username.strip()
    op = (
        await session.execute(select(Operator).where(Operator.username == username))
    ).scalar_one_or_none()
    if op is not None:
        if bootstrap and not op.is_admin:
            op.is_admin = True
            await session.flush()
        return op

    op = Operator(username=username, is_admin=bootstrap)
    session.add(op)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        op = (
            await session.execute(select(Operator).where(Operator.username == username))
        ).scalar_one()
        if bootstrap and not op.is_admin:
            op.is_admin = True
            await session.flush()
    return op


async def list_operators(session: AsyncSession) -> list[Operator]:
    result = await session.execute(select(Operator).order_by(Operator.username))
    return list(result.scalars().all())


async def patch_operator(
    session: AsyncSession,
    *,
    operator_id: uuid.UUID,
    is_admin: bool | None,
    is_active: bool | None,
) -> Operator:
    op = (
        await session.execute(select(Operator).where(Operator.id == operator_id))
    ).scalar_one()
    if is_admin is not None:
        op.is_admin = is_admin
    if is_active is not None:
        op.is_active = is_active
    await session.flush()
    return op
