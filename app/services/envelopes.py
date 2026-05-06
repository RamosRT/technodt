"""Envelope service — create, lookup, add/remove documents, seal."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    AppError,
    DocumentAlreadyInEnvelope,
    EnvelopeNotDraft,
    EnvelopeNotFound,
    InvalidSealPayload,
)
from app.models import AuditLog, Branch, Envelope, EnvelopeDocument, EnvelopeStatus, Signer
from app.services.audit import write_event
from app.services.barcode import doc_barcode_to_guid, generate_envelope_codes
from app.services.odata import OneCClient

MAX_CODE_RETRIES = 5


def _date_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
    end = datetime.combine(date_to, time.max, tzinfo=UTC) if date_to else None
    return start, end


def _envelope_filters(
    stmt: Select,
    *,
    status: EnvelopeStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
) -> Select:
    if status is not None:
        stmt = stmt.where(Envelope.status == status)
    start, end = _date_bounds(date_from, date_to)
    if start is not None:
        stmt = stmt.where(Envelope.created_at >= start)
    if end is not None:
        stmt = stmt.where(Envelope.created_at <= end)
    if branch_id is not None:
        stmt = stmt.where(
            or_(
                Envelope.origin_branch_id == branch_id,
                Envelope.destination_branch_id == branch_id,
            )
        )
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Envelope.number.ilike(term), Envelope.barcode.ilike(term)))
    return stmt


async def list_envelopes(
    session: AsyncSession,
    *,
    status: EnvelopeStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    base = select(Envelope)
    base = _envelope_filters(
        base,
        status=status,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
        search=search,
    )
    total = (
        await session.execute(
            _envelope_filters(
                select(func.count(Envelope.id)),
                status=status,
                date_from=date_from,
                date_to=date_to,
                branch_id=branch_id,
                search=search,
            )
        )
    ).scalar_one()

    result = await session.execute(
        base.options(selectinload(Envelope.documents))
        .order_by(Envelope.created_at.desc(), Envelope.number.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
    )
    envelopes = list(result.scalars().all())

    branch_ids = {
        branch_id
        for env in envelopes
        for branch_id in (env.origin_branch_id, env.destination_branch_id)
        if branch_id is not None
    }
    branch_names = {}
    if branch_ids:
        rows = (await session.execute(select(Branch.id, Branch.name).where(Branch.id.in_(branch_ids)))).all()
        branch_names = {row.id: row.name for row in rows}

    items = []
    for env in envelopes:
        missing_count = 0
        if env.status is EnvelopeStatus.verified_with_discrepancy:
            missing_count = sum(1 for doc in env.documents if doc.scanned_at_verification is None)
        items.append(
            {
                "id": env.id,
                "number": env.number,
                "barcode": env.barcode,
                "status": env.status,
                "created_at": env.created_at,
                "sealed_at": env.sealed_at,
                "verified_at": env.verified_at,
                "created_by": env.created_by,
                "verified_by": env.verified_by,
                "origin_branch_id": env.origin_branch_id,
                "destination_branch_id": env.destination_branch_id,
                "origin_branch_name": branch_names.get(env.origin_branch_id),
                "destination_branch_name": branch_names.get(env.destination_branch_id),
                "document_count": len(env.documents),
                "missing_count": missing_count,
            }
        )
    return items, total


async def list_recent_for_operator(
    session: AsyncSession,
    *,
    operator: str,
    limit: int = 5,
) -> list[Envelope]:
    activity = (
        select(
            AuditLog.envelope_id.label("envelope_id"),
            func.max(AuditLog.at).label("last_activity_at"),
        )
        .where(AuditLog.actor == operator, AuditLog.envelope_id.is_not(None))
        .group_by(AuditLog.envelope_id)
        .subquery()
    )
    result = await session.execute(
        select(Envelope)
        .join(activity, Envelope.id == activity.c.envelope_id)
        .where(Envelope.status.in_([EnvelopeStatus.draft, EnvelopeStatus.sealed]))
        .options(selectinload(Envelope.documents))
        .order_by(activity.c.last_activity_at.desc(), Envelope.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Task 15: create_envelope
# ---------------------------------------------------------------------------


async def discard_empty_drafts(session: AsyncSession, *, operator: str) -> int:
    """Remove abandoned draft envelopes for an operator before starting a new one."""
    empty_ids = list(
        (
            await session.execute(
                select(Envelope.id)
                .outerjoin(EnvelopeDocument, EnvelopeDocument.envelope_id == Envelope.id)
                .where(
                    Envelope.status == EnvelopeStatus.draft,
                    Envelope.created_by == operator,
                )
                .group_by(Envelope.id)
                .having(func.count(EnvelopeDocument.id) == 0)
            )
        ).scalars().all()
    )
    if not empty_ids:
        return 0

    await session.execute(delete(AuditLog).where(AuditLog.envelope_id.in_(empty_ids)))
    await session.execute(delete(Envelope).where(Envelope.id.in_(empty_ids)))
    await session.flush()
    return len(empty_ids)


async def create_envelope(session: AsyncSession, *, operator: str, discard_empty: bool = True) -> Envelope:
    if discard_empty:
        await discard_empty_drafts(session, operator=operator)

    last_exc: Exception | None = None
    for _ in range(MAX_CODE_RETRIES):
        number, barcode = generate_envelope_codes()
        env = Envelope(
            number=number,
            barcode=barcode,
            status=EnvelopeStatus.draft,
            created_by=operator,
        )
        session.add(env)
        try:
            await session.flush()
        except IntegrityError as e:
            last_exc = e
            await session.rollback()
            continue
        await write_event(session, envelope_id=env.id, event="create", actor=operator,
                          payload={"number": number, "barcode": barcode})
        return env
    raise RuntimeError(
        f"could not generate unique envelope codes after {MAX_CODE_RETRIES} retries"
    ) from last_exc


# ---------------------------------------------------------------------------
# Task 16: get_by_id, get_by_barcode
# ---------------------------------------------------------------------------


async def get_by_id(session: AsyncSession, envelope_id: uuid.UUID) -> Envelope:
    stmt = (
        select(Envelope)
        .where(Envelope.id == envelope_id)
        .options(selectinload(Envelope.documents))
    )
    env = (await session.execute(stmt)).scalar_one_or_none()
    if env is None:
        raise EnvelopeNotFound(f"Конверт {envelope_id} не найден")
    return env


async def get_by_barcode(session: AsyncSession, barcode: str) -> Envelope:
    stmt = (
        select(Envelope)
        .where(Envelope.barcode == barcode)
        .options(selectinload(Envelope.documents))
    )
    env = (await session.execute(stmt)).scalar_one_or_none()
    if env is None:
        raise EnvelopeNotFound(f"Конверт со ШК {barcode} не найден")
    return env


# ---------------------------------------------------------------------------
# Task 17: add_document
# ---------------------------------------------------------------------------


async def add_document(
    session: AsyncSession,
    *,
    envelope: Envelope,
    barcode: str,
    operator: str,
    one_c: OneCClient,
) -> EnvelopeDocument:
    if envelope.status is not EnvelopeStatus.draft:
        raise EnvelopeNotDraft("Конверт уже запечатан")

    guid = doc_barcode_to_guid(barcode)

    existing = (
        await session.execute(
            select(EnvelopeDocument).where(
                EnvelopeDocument.envelope_id == envelope.id,
                EnvelopeDocument.doc_guid == guid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DocumentAlreadyInEnvelope("Этот документ уже добавлен в конверт")

    normalized = await one_c.lookup_document_with_related(guid)
    doc = EnvelopeDocument(
        envelope_id=envelope.id,
        doc_barcode=barcode,
        doc_guid=guid,
        doc_entity=normalized.entity,
        doc_kind=normalized.doc_kind,
        doc_number=normalized.doc_number,
        doc_date=normalized.doc_date,
        related_realization_number=normalized.related_realization_number,
        related_realization_date=normalized.related_realization_date,
        raw_1c_payload=normalized.raw_payload,
    )
    session.add(doc)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise DocumentAlreadyInEnvelope("Этот документ уже добавлен в конверт") from e

    await write_event(
        session,
        envelope_id=envelope.id,
        event="add_doc",
        actor=operator,
        payload={
            "doc_guid": str(guid),
            "doc_kind": normalized.doc_kind,
            "doc_number": normalized.doc_number,
        },
    )
    return doc


# ---------------------------------------------------------------------------
# Task 18: remove_document
# ---------------------------------------------------------------------------


async def remove_document(
    session: AsyncSession,
    *,
    envelope: Envelope,
    doc_id: uuid.UUID,
    operator: str,
) -> None:
    if envelope.status is not EnvelopeStatus.draft:
        raise EnvelopeNotDraft("Конверт уже запечатан")
    doc = (
        await session.execute(
            select(EnvelopeDocument).where(
                EnvelopeDocument.envelope_id == envelope.id,
                EnvelopeDocument.id == doc_id,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return  # idempotent
    payload = {"doc_guid": str(doc.doc_guid), "doc_number": doc.doc_number}
    await session.delete(doc)
    await write_event(session, envelope_id=envelope.id, event="remove_doc", actor=operator, payload=payload)


# ---------------------------------------------------------------------------
# Task 19: seal
# ---------------------------------------------------------------------------


async def seal(
    session: AsyncSession,
    *,
    envelope: Envelope,
    signer_sender_id: uuid.UUID,
    signer_receiver_id: uuid.UUID,
    origin_branch_id: uuid.UUID,
    destination_branch_id: uuid.UUID | None,
    notes: str | None,
    operator: str,
) -> Envelope:
    if envelope.status is not EnvelopeStatus.draft:
        raise EnvelopeNotDraft("Конверт уже запечатан")

    # Always query the DB for document count — the relationship attribute may be
    # expired after a commit() and trigger an illegal sync lazy-load in async context.
    doc_count = len(
        (
            await session.execute(
                select(EnvelopeDocument).where(EnvelopeDocument.envelope_id == envelope.id)
            )
        ).scalars().all()
    )
    if doc_count == 0:
        raise InvalidSealPayload("В конверте нет ни одного документа")

    branch_ids = [origin_branch_id]
    if destination_branch_id is not None:
        branch_ids.append(destination_branch_id)
    branches = (
        await session.execute(
            select(Branch).where(Branch.id.in_(branch_ids))
        )
    ).scalars().all()
    if len(branches) != len(set(branch_ids)) or any(not b.is_active for b in branches):
        raise InvalidSealPayload("Указан несуществующий или неактивный филиал")

    signers = (
        await session.execute(
            select(Signer).where(Signer.id.in_([signer_sender_id, signer_receiver_id]))
        )
    ).scalars().all()
    needed = {signer_sender_id, signer_receiver_id}
    if {s.id for s in signers} != needed or any(not s.is_active for s in signers):
        raise InvalidSealPayload("Указан несуществующий или неактивный подписант")

    envelope.status = EnvelopeStatus.sealed
    envelope.sealed_at = datetime.now(UTC)
    envelope.signer_sender_id = signer_sender_id
    envelope.signer_receiver_id = signer_receiver_id
    envelope.origin_branch_id = origin_branch_id
    envelope.destination_branch_id = destination_branch_id
    envelope.notes = notes

    await write_event(
        session,
        envelope_id=envelope.id,
        event="seal",
        actor=operator,
        payload={
            "origin": str(origin_branch_id),
            "destination": str(destination_branch_id) if destination_branch_id else None,
        },
    )
    return envelope


async def unseal(
    session: AsyncSession,
    *,
    envelope: Envelope,
    reason: str,
    operator: str,
) -> Envelope:
    if envelope.status is not EnvelopeStatus.sealed:
        raise AppError("Распечатать можно только запечатанный конверт", status_code=409, code="envelope_not_sealed")
    reason = reason.strip()
    if not reason:
        raise InvalidSealPayload("Укажите причину распечатки")

    envelope.status = EnvelopeStatus.draft
    envelope.sealed_at = None

    await write_event(
        session,
        envelope_id=envelope.id,
        event="unseal",
        actor=operator,
        payload={"reason": reason},
    )
    return envelope
