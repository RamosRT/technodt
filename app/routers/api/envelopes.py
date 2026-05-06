import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_operator
from app.db import get_session, get_session_factory
from app.parsing import optional_query_date
from app.deps import get_one_c_client
from app.exceptions import AppError
from app.models import EnvelopeDocument, EnvelopeStatus
from app.schemas.document import DocumentAddRequest, DocumentOut
from app.schemas.envelope import EnvelopeOut, SealRequest, UnsealRequest
from app.services import envelopes as svc
from app.services import printing
from app.services import system_settings as settings_svc
from app.services.onec_marks import fire_seal_marks
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


@router.get("")
async def list_envelopes(
    status_filter: str | None = Query(default=None, alias="status"),
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    branch_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    status_value = EnvelopeStatus(status_filter) if status_filter else None
    branch_uuid = uuid.UUID(branch_id) if branch_id else None
    items, total = await svc.list_envelopes(
        session,
        status=status_value,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_uuid,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/recent", response_model=list[EnvelopeOut])
async def recent_envelopes(
    limit: int = Query(default=5, ge=1, le=5),
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_recent_for_operator(session, operator=operator, limit=limit)


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
    one_c: OneCClient = Depends(get_one_c_client),
):
    docs = (
        await session.execute(
            select(EnvelopeDocument).where(EnvelopeDocument.envelope_id == envelope_id)
        )
    ).scalars().all()
    enable_marks = await settings_svc.is_1c_timestamps_enabled(session)
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
    fire_seal_marks(
        one_c,
        sealed.id,
        list(docs),
        sealed.sealed_at,
        get_session_factory(),
        enabled=enable_marks,
    )
    return await svc.get_by_id(session, sealed.id)


@router.post("/{envelope_id}/unseal", response_model=EnvelopeOut)
async def unseal_envelope(
    envelope_id: uuid.UUID,
    body: UnsealRequest,
    _admin: None = require_admin(),
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    unsealed = await svc.unseal(session, envelope=envelope, reason=body.reason, operator=operator)
    await session.commit()
    return await svc.get_by_id(session, unsealed.id)


@router.get("/{envelope_id}/print/inventory")
async def print_inventory(
    envelope_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    pdf = await printing.render_inventory_pdf(session, envelope_id)
    envelope = await svc.get_by_id(session, envelope_id)
    filename = f"inventory_{envelope.number.replace('ТА-', 'TA-')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{envelope_id}/print/label")
async def print_label(
    envelope_id: uuid.UUID,
    format: str = Query(default="pdf", pattern="^(pdf|zpl)$"),
    dpi: int = Query(default=200, ge=200, le=300),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    filename_base = f"label_{envelope.number.replace('ТА-', 'TA-')}"

    if format == "zpl":
        zpl = printing.render_label_zpl(envelope, dpi=dpi)
        return Response(
            content=zpl.encode("utf-8"),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.zpl"'},
        )

    pdf = await printing.render_label_pdf(session, envelope_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename_base}.pdf"'},
    )


@router.get("/{envelope_id}/print/discrepancy-act")
async def print_discrepancy_act(
    envelope_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    if envelope.status is not EnvelopeStatus.verified_with_discrepancy:
        raise AppError("Акт о расхождениях доступен только для конвертов с расхождением", status_code=409)

    pdf = await printing.render_discrepancy_act_pdf(session, envelope_id)
    filename = f"discrepancy_act_{envelope.number.replace('ТА-', 'TA-')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
