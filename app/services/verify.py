import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EnvelopeNotDraft, VerificationUnscanned
from app.models import Envelope, EnvelopeDocument, EnvelopeStatus
from app.services.audit import write_event


@dataclass
class ScanResult:
    matched: bool
    doc_id: uuid.UUID | None = None
    scanned_at: datetime | None = None
    reason: str | None = None


@dataclass
class FinishResult:
    status: str
    missing_docs: list[uuid.UUID]


async def start(session: AsyncSession, *, envelope: Envelope, operator: str) -> Envelope:
    if envelope.status is not EnvelopeStatus.sealed:
        raise EnvelopeNotDraft(f"Конверт в статусе {envelope.status.value} — сверка невозможна")
    envelope.verified_by = operator
    await write_event(session, envelope_id=envelope.id, event="verify_start", actor=operator)
    return envelope


async def scan(session: AsyncSession, *, envelope: Envelope, barcode: str, operator: str) -> ScanResult:
    doc = (
        await session.execute(
            select(EnvelopeDocument).where(
                EnvelopeDocument.envelope_id == envelope.id,
                EnvelopeDocument.doc_barcode == barcode,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        await write_event(session, envelope_id=envelope.id, event="verify_scan", actor=operator,
                          payload={"barcode": barcode, "matched": False})
        return ScanResult(matched=False, reason="not_in_envelope")
    if doc.scanned_at_verification is not None:
        await write_event(
            session,
            envelope_id=envelope.id,
            event="verify_scan",
            actor=operator,
            payload={
                "barcode": barcode,
                "matched": True,
                "doc_id": str(doc.id),
                "duplicate": True,
            },
        )
        return ScanResult(
            matched=True,
            doc_id=doc.id,
            scanned_at=doc.scanned_at_verification,
            reason="already_scanned",
        )
    if doc.scanned_at_verification is None:
        doc.scanned_at_verification = datetime.now(timezone.utc)
    await write_event(session, envelope_id=envelope.id, event="verify_scan", actor=operator,
                      payload={"barcode": barcode, "matched": True, "doc_id": str(doc.id)})
    return ScanResult(matched=True, doc_id=doc.id, scanned_at=doc.scanned_at_verification)


async def finish(session: AsyncSession, *, envelope: Envelope, force: bool, operator: str) -> FinishResult:
    if envelope.status is not EnvelopeStatus.sealed:
        raise EnvelopeNotDraft(f"Конверт в статусе {envelope.status.value} — нельзя завершить сверку")
    docs = (
        await session.execute(
            select(EnvelopeDocument).where(EnvelopeDocument.envelope_id == envelope.id)
        )
    ).scalars().all()
    missing = [d.id for d in docs if d.scanned_at_verification is None]
    if missing and not force:
        raise VerificationUnscanned(f"Не отсканировано документов: {len(missing)}")
    envelope.status = EnvelopeStatus.verified_with_discrepancy if missing else EnvelopeStatus.verified
    envelope.verified_at = datetime.now(timezone.utc)
    await write_event(session, envelope_id=envelope.id, event="verify_finish", actor=operator,
                      payload={"force": force, "missing": [str(m) for m in missing]})
    return FinishResult(status=envelope.status.value, missing_docs=missing)
