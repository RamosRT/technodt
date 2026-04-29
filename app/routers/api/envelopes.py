import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.deps import get_one_c_client
from app.schemas.document import DocumentAddRequest, DocumentOut
from app.schemas.envelope import EnvelopeOut, SealRequest
from app.services import envelopes as svc
from app.services.odata import OneCClient

router = APIRouter(prefix="/api/envelopes", tags=["envelopes"])


@router.post("", response_model=EnvelopeOut, status_code=status.HTTP_201_CREATED)
async def create_envelope(
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    env = await svc.create_envelope(session, operator=operator)
    await session.commit()
    return await svc.get_by_id(session, env.id)


@router.get("/by-barcode/{barcode}", response_model=EnvelopeOut)
async def get_envelope_by_barcode(barcode: str, session: AsyncSession = Depends(get_session)):
    return await svc.get_by_barcode(session, barcode)


@router.get("/{envelope_id}", response_model=EnvelopeOut)
async def get_envelope(envelope_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await svc.get_by_id(session, envelope_id)


@router.post("/{envelope_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def add_document(
    envelope_id: uuid.UUID,
    body: DocumentAddRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
):
    envelope = await svc.get_by_id(session, envelope_id)
    doc = await svc.add_document(session, envelope=envelope, barcode=body.barcode,
                                  operator=operator, one_c=one_c)
    await session.commit()
    return doc


@router.delete("/{envelope_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    envelope_id: uuid.UUID,
    doc_id: uuid.UUID,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    await svc.remove_document(session, envelope=envelope, doc_id=doc_id, operator=operator)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{envelope_id}/seal", response_model=EnvelopeOut)
async def seal_envelope(
    envelope_id: uuid.UUID,
    body: SealRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    sealed = await svc.seal(
        session, envelope=envelope,
        signer_sender_id=body.signer_sender_id,
        signer_receiver_id=body.signer_receiver_id,
        origin_branch_id=body.origin_branch_id,
        destination_branch_id=body.destination_branch_id,
        notes=body.notes, operator=operator,
    )
    await session.commit()
    return await svc.get_by_id(session, sealed.id)
