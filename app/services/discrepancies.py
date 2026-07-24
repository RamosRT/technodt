from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppError
from app.models import Envelope, EnvelopeDocument, EnvelopeStatus
from app.services.audit import write_event


@dataclass
class DiscrepancyStats:
    active: int
    resolved: int

    @property
    def total(self) -> int:
        return self.active + self.resolved


def _discrepancy_condition():
    return (
        (Envelope.status == EnvelopeStatus.verified_with_discrepancy)
        & EnvelopeDocument.scanned_at_verification.is_(None)
    )


def _partner_name(document: EnvelopeDocument) -> str | None:
    payload = document.raw_1c_payload or {}
    partner = payload.get("Партнер") or {}
    receiver = payload.get("СкладПолучатель") or {}
    return (
        partner.get("НаименованиеПолное")
        or partner.get("Description")
        or receiver.get("Description")
    )


async def list_discrepancies(
    session: AsyncSession,
    *,
    limit: int = 200,
) -> tuple[list[dict], DiscrepancyStats]:
    stmt = (
        select(EnvelopeDocument, Envelope)
        .join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
        .where(_discrepancy_condition())
        .order_by(
            case((EnvelopeDocument.discrepancy_resolved_at.is_(None), 0), else_=1),
            Envelope.verified_at.desc(),
            EnvelopeDocument.doc_number,
        )
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).all())
    counts = (
        await session.execute(
            select(
                func.count(EnvelopeDocument.id),
                func.count(EnvelopeDocument.id).filter(
                    EnvelopeDocument.discrepancy_resolved_at.is_(None)
                ),
            )
            .join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
            .where(_discrepancy_condition())
        )
    ).one()
    total_count, active = counts
    resolved = total_count - active
    items = [
        {
            "id": document.id,
            "doc_barcode": document.doc_barcode,
            "doc_kind": document.doc_kind,
            "doc_number": document.doc_number,
            "doc_date": document.doc_date,
            "partner_name": _partner_name(document),
            "envelope_id": envelope.id,
            "envelope_number": envelope.number,
            "lost_at": envelope.verified_at,
            "resolved_at": document.discrepancy_resolved_at,
            "resolved_by": document.discrepancy_resolved_by,
            "is_resolved": document.discrepancy_resolved_at is not None,
        }
        for document, envelope in rows
    ]
    return items, DiscrepancyStats(active=active, resolved=resolved)


async def resolve_by_barcode(
    session: AsyncSession,
    *,
    barcode: str,
    operator: str,
) -> EnvelopeDocument:
    barcode = barcode.strip()
    if not barcode:
        raise AppError("Отсканируйте штрихкод документа", code="discrepancy_barcode_empty")

    stmt = (
        select(EnvelopeDocument, Envelope)
        .join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
        .where(
            _discrepancy_condition(),
            EnvelopeDocument.doc_barcode == barcode,
            EnvelopeDocument.discrepancy_resolved_at.is_(None),
        )
        .order_by(Envelope.verified_at.desc())
        .with_for_update(of=EnvelopeDocument)
    )
    matches = list((await session.execute(stmt)).all())
    if not matches:
        resolved_match = (
            await session.execute(
                select(EnvelopeDocument)
                .join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
                .where(
                    _discrepancy_condition(),
                    EnvelopeDocument.doc_barcode == barcode,
                    EnvelopeDocument.discrepancy_resolved_at.is_not(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if resolved_match is not None:
            raise AppError(
                "Этот документ уже отмечен как сданный",
                status_code=409,
                code="discrepancy_already_resolved",
            )
        raise AppError(
            "Документ не числится в активных расхождениях",
            status_code=404,
            code="discrepancy_not_found",
        )
    if len(matches) > 1:
        raise AppError(
            "Документ найден в нескольких активных расхождениях — обратитесь к администратору",
            status_code=409,
            code="discrepancy_ambiguous",
        )

    document, envelope = matches[0]
    now = datetime.now(UTC)
    document.discrepancy_resolved_at = now
    document.discrepancy_resolved_by = operator
    await write_event(
        session,
        envelope_id=envelope.id,
        event="discrepancy_resolved",
        actor=operator,
        payload={
            "doc_id": str(document.id),
            "doc_barcode": document.doc_barcode,
            "doc_number": document.doc_number,
            "lost_at": envelope.verified_at.isoformat() if envelope.verified_at else None,
            "resolved_at": now.isoformat(),
        },
    )
    return document


async def undo_resolution(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    reason: str,
    operator: str,
) -> EnvelopeDocument:
    reason = reason.strip()
    if not reason:
        raise AppError(
            "Укажите причину отмены",
            code="discrepancy_undo_reason_required",
        )
    row = (
        await session.execute(
            select(EnvelopeDocument, Envelope)
            .join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
            .where(
                EnvelopeDocument.id == document_id,
                _discrepancy_condition(),
            )
            .with_for_update(of=EnvelopeDocument)
        )
    ).one_or_none()
    if row is None:
        raise AppError(
            "Документ не относится к расхождениям",
            status_code=404,
            code="discrepancy_not_found",
        )
    document, envelope = row
    if document.discrepancy_resolved_at is None:
        raise AppError(
            "Документ ещё не был отмечен как сданный",
            status_code=409,
            code="discrepancy_not_resolved",
        )

    previous_at = document.discrepancy_resolved_at
    previous_by = document.discrepancy_resolved_by
    document.discrepancy_resolved_at = None
    document.discrepancy_resolved_by = None
    await write_event(
        session,
        envelope_id=envelope.id,
        event="discrepancy_resolution_undo",
        actor=operator,
        payload={
            "doc_id": str(document.id),
            "doc_barcode": document.doc_barcode,
            "doc_number": document.doc_number,
            "reason": reason,
            "previous_resolved_at": previous_at.isoformat(),
            "previous_resolved_by": previous_by,
        },
    )
    return document
