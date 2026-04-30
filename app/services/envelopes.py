"""Envelope service — create, lookup, add/remove documents, seal."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    DocumentAlreadyInEnvelope,
    EnvelopeNotDraft,
    EnvelopeNotFound,
    InvalidSealPayload,
)
from app.models import Branch, Envelope, EnvelopeDocument, EnvelopeStatus, Signer
from app.services.audit import write_event
from app.services.barcode import doc_barcode_to_guid, generate_envelope_codes
from app.services.odata import OneCClient


MAX_CODE_RETRIES = 5


# ---------------------------------------------------------------------------
# Task 15: create_envelope
# ---------------------------------------------------------------------------


async def create_envelope(session: AsyncSession, *, operator: str) -> Envelope:
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
    envelope.sealed_at = datetime.now(timezone.utc)
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
