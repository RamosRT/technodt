import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.schemas.operator import OperatorCreate, OperatorOut, OperatorPatch
from app.services.operators import ensure_operator, list_operators, patch_operator

router = APIRouter(prefix="/api/operators", tags=["operators"])


@router.get("", response_model=list[OperatorOut])
async def get_operators(
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    return await list_operators(session)


@router.post("", response_model=OperatorOut, status_code=status.HTTP_201_CREATED)
async def create_operator(
    body: OperatorCreate,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    op = await ensure_operator(session, body.username, bootstrap=body.is_admin)
    await session.commit()
    return op


@router.patch("/{operator_id}", response_model=OperatorOut)
async def update_operator(
    operator_id: uuid.UUID,
    body: OperatorPatch,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    op = await patch_operator(
        session,
        operator_id=operator_id,
        is_admin=body.is_admin,
        is_active=body.is_active,
    )
    await session.commit()
    return op
