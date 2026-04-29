import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.envelope import EnvelopeOut
from app.schemas.verify import (
    VerifyFinishRequest, VerifyFinishResponse, VerifyScanRequest, VerifyScanResponse,
)
from app.services import envelopes as env_svc
from app.services import verify as svc

router = APIRouter(prefix="/api/envelopes", tags=["verify"])


@router.post("/{envelope_id}/verify/start", response_model=EnvelopeOut)
async def verify_start(
    envelope_id: uuid.UUID,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    await svc.start(session, envelope=envelope, operator=operator)
    await session.commit()
    return await env_svc.get_by_id(session, envelope_id)


@router.post("/{envelope_id}/verify/scan", response_model=VerifyScanResponse)
async def verify_scan(
    envelope_id: uuid.UUID,
    body: VerifyScanRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    res = await svc.scan(session, envelope=envelope, barcode=body.barcode, operator=operator)
    await session.commit()
    return VerifyScanResponse(matched=res.matched, doc_id=res.doc_id,
                              scanned_at=res.scanned_at, reason=res.reason)


@router.post("/{envelope_id}/verify/finish", response_model=VerifyFinishResponse)
async def verify_finish(
    envelope_id: uuid.UUID,
    body: VerifyFinishRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    res = await svc.finish(session, envelope=envelope, force=body.force, operator=operator)
    await session.commit()
    return VerifyFinishResponse(status=res.status, missing_docs=res.missing_docs)
