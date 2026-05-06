import csv
import io
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Branch, Envelope, EnvelopeDocument, EnvelopeStatus

LEGACY_TRANSFER_KIND = "Перемещение товаров"
SHORT_TRANSFER_KIND = "ПРМ"


def _canonical_doc_kind(value: str) -> str:
    return SHORT_TRANSFER_KIND if value == LEGACY_TRANSFER_KIND else value


def _date_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
    end = datetime.combine(date_to, time.max, tzinfo=UTC) if date_to else None
    return start, end


def _status_expr(status: str | None):
    if status == "verified":
        return EnvelopeDocument.scanned_at_verification.is_not(None)
    if status == "in_transit":
        return (
            (Envelope.status == EnvelopeStatus.sealed)
            & (EnvelopeDocument.scanned_at_verification.is_(None))
        )
    if status == "missing":
        return (
            (Envelope.status == EnvelopeStatus.verified_with_discrepancy)
            & (EnvelopeDocument.scanned_at_verification.is_(None))
        )
    return None


def _base_documents_stmt(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    doc_kind: str | None = None,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
):
    stmt = select(EnvelopeDocument, Envelope).join(Envelope, EnvelopeDocument.envelope_id == Envelope.id)
    start, end = _date_bounds(date_from, date_to)
    if start is not None:
        stmt = stmt.where(EnvelopeDocument.added_at >= start)
    if end is not None:
        stmt = stmt.where(EnvelopeDocument.added_at <= end)
    if doc_kind:
        if doc_kind == SHORT_TRANSFER_KIND:
            stmt = stmt.where(EnvelopeDocument.doc_kind.in_([SHORT_TRANSFER_KIND, LEGACY_TRANSFER_KIND]))
        else:
            stmt = stmt.where(EnvelopeDocument.doc_kind == doc_kind)
    status_filter = _status_expr(status)
    if status_filter is not None:
        stmt = stmt.where(status_filter)
    if branch_id is not None:
        stmt = stmt.where(
            or_(
                Envelope.origin_branch_id == branch_id,
                Envelope.destination_branch_id == branch_id,
            )
        )
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                EnvelopeDocument.doc_number.ilike(term),
                EnvelopeDocument.doc_barcode.ilike(term),
                Envelope.number.ilike(term),
                Envelope.barcode.ilike(term),
            )
        )
    return stmt


def document_status(doc: EnvelopeDocument, envelope: Envelope) -> str:
    if doc.scanned_at_verification is not None:
        return "verified"
    if envelope.status is EnvelopeStatus.verified_with_discrepancy:
        return "missing"
    if envelope.status is EnvelopeStatus.sealed:
        return "in_transit"
    return "draft"


async def list_documents(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    doc_kind: str | None = None,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int, dict[str, int]]:
    stmt = _base_documents_stmt(
        date_from=date_from,
        date_to=date_to,
        doc_kind=doc_kind,
        status=status,
        branch_id=branch_id,
        search=search,
    )
    count_stmt = stmt.with_only_columns(func.count(EnvelopeDocument.id)).order_by(None)
    total = (await session.execute(count_stmt)).scalar_one()

    rows = (
        await session.execute(
            stmt.order_by(EnvelopeDocument.added_at.desc(), EnvelopeDocument.doc_number.desc())
            .offset((max(page, 1) - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    branch_ids = {
        branch_id
        for _, envelope in rows
        for branch_id in (envelope.origin_branch_id, envelope.destination_branch_id)
        if branch_id is not None
    }
    branch_names = {}
    if branch_ids:
        branch_rows = (await session.execute(select(Branch.id, Branch.name).where(Branch.id.in_(branch_ids)))).all()
        branch_names = {row.id: row.name for row in branch_rows}

    items = []
    summary = {"total": total, "verified": 0, "in_transit": 0, "missing": 0}
    all_rows = (
        await session.execute(
            _base_documents_stmt(
                date_from=date_from,
                date_to=date_to,
                doc_kind=doc_kind,
                status=None,
                branch_id=branch_id,
                search=search,
            )
        )
    ).all()
    for doc, envelope in all_rows:
        state = document_status(doc, envelope)
        if state in summary:
            summary[state] += 1

    for doc, envelope in rows:
        state = document_status(doc, envelope)
        items.append(
            {
                "id": doc.id,
                "doc_barcode": doc.doc_barcode,
                "doc_guid": doc.doc_guid,
                "doc_entity": doc.doc_entity,
                "doc_kind": _canonical_doc_kind(doc.doc_kind),
                "doc_number": doc.doc_number,
                "doc_date": doc.doc_date,
                "added_at": doc.added_at,
                "scanned_at_verification": doc.scanned_at_verification,
                "status": state,
                "envelope_id": envelope.id,
                "envelope_number": envelope.number,
                "envelope_barcode": envelope.barcode,
                "envelope_status": envelope.status,
                "created_by": envelope.created_by,
                "sealed_at": envelope.sealed_at,
                "verified_by": envelope.verified_by,
                "origin_branch_name": branch_names.get(envelope.origin_branch_id),
                "destination_branch_name": branch_names.get(envelope.destination_branch_id),
            }
        )
    return items, total, summary


def build_documents_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Тип",
            "Номер документа",
            "Дата документа",
            "Штрихкод",
            "Конверт",
            "Статус",
            "Добавлен",
            "Запечатан",
            "Верифицирован",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["doc_kind"],
                row["doc_number"],
                row["doc_date"].isoformat(),
                row["doc_barcode"],
                row["envelope_number"],
                row["status"],
                row["added_at"].isoformat() if row["added_at"] else "",
                row["sealed_at"].isoformat() if row["sealed_at"] else "",
                row["scanned_at_verification"].isoformat() if row["scanned_at_verification"] else "",
            ]
        )
    return output.getvalue()
