import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.dictionary import (
    BranchCreate,
    BranchOut,
    BranchPatch,
    SignerCreate,
    SignerOut,
    SignerPatch,
)
from app.services import dictionaries as svc

router = APIRouter(tags=["dictionaries"])


@router.get("/api/branches", response_model=list[BranchOut])
async def list_branches(active: bool = True, session: AsyncSession = Depends(get_session)):
    return await svc.list_branches(session, only_active=active)


@router.post("/api/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: BranchCreate,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    b = await svc.create_branch(session, name=body.name, operator=operator)
    await session.commit()
    return b


@router.patch("/api/branches/{branch_id}", response_model=BranchOut)
async def patch_branch(
    branch_id: uuid.UUID,
    body: BranchPatch,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    b = await svc.patch_branch(session, branch_id=branch_id,
                                is_active=body.is_active, name=body.name, operator=operator)
    await session.commit()
    return b


@router.get("/api/signers", response_model=list[SignerOut])
async def list_signers(active: bool = True, session: AsyncSession = Depends(get_session)):
    return await svc.list_signers(session, only_active=active)


@router.post("/api/signers", response_model=SignerOut, status_code=status.HTTP_201_CREATED)
async def create_signer(
    body: SignerCreate,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    s = await svc.create_signer(session, last_name=body.last_name, first_name=body.first_name,
                                 operator=operator)
    await session.commit()
    return s


@router.patch("/api/signers/{signer_id}", response_model=SignerOut)
async def patch_signer(
    signer_id: uuid.UUID,
    body: SignerPatch,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    s = await svc.patch_signer(session, signer_id=signer_id,
                                last_name=body.last_name, first_name=body.first_name,
                                is_active=body.is_active, operator=operator)
    await session.commit()
    return s
