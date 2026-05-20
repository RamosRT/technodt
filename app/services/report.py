import csv
import io
import uuid
from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Branch,
    Envelope,
    EnvelopeDocument,
    EnvelopeStatus,
    OneCDocument,
    OneCMarkLog,
)
from app.services.odata import PROP_REGISTERED, PROP_SEALED, PROP_VERIFIED


async def list_report_documents(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    partner_search: str | None = None,
    number_search: str | None = None,
    only_archived: bool = False,
    only_without_envelope: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    OriginBranch = aliased(Branch, name="origin_branch")
    DestBranch = aliased(Branch, name="dest_branch")

    # For each document, pick the earliest envelope (registration moment)
    first_env_sub = (
        select(
            EnvelopeDocument.doc_guid,
            func.min(EnvelopeDocument.added_at).label("registered_at"),
        )
        .group_by(EnvelopeDocument.doc_guid)
        .subquery("first_env")
    )

    # Mark log subqueries — latest successful mark per property per doc
    def mark_sub(prop_key: uuid.UUID, label: str):
        return (
            select(
                OneCMarkLog.doc_guid,
                func.max(OneCMarkLog.attempted_at).label(label),
            )
            .where(
                and_(
                    OneCMarkLog.property_key == prop_key,
                    OneCMarkLog.status == "success",
                )
            )
            .group_by(OneCMarkLog.doc_guid)
            .subquery(label)
        )

    mark_reg = mark_sub(PROP_REGISTERED, "mark_reg")
    mark_seal = mark_sub(PROP_SEALED, "mark_seal")
    mark_ver = mark_sub(PROP_VERIFIED, "mark_ver")

    stmt = (
        select(
            OneCDocument,
            EnvelopeDocument,
            Envelope,
            OriginBranch.name.label("origin_branch_name"),
            DestBranch.name.label("dest_branch_name"),
            first_env_sub.c.registered_at,
            mark_reg.c.mark_reg,
            mark_seal.c.mark_seal,
            mark_ver.c.mark_ver,
        )
        .outerjoin(first_env_sub, first_env_sub.c.doc_guid == OneCDocument.guid)
        .outerjoin(
            EnvelopeDocument,
            and_(
                EnvelopeDocument.doc_guid == OneCDocument.guid,
                EnvelopeDocument.added_at == first_env_sub.c.registered_at,
            ),
        )
        .outerjoin(Envelope, Envelope.id == EnvelopeDocument.envelope_id)
        .outerjoin(OriginBranch, OriginBranch.id == Envelope.origin_branch_id)
        .outerjoin(DestBranch, DestBranch.id == Envelope.destination_branch_id)
        .outerjoin(mark_reg, mark_reg.c.doc_guid == OneCDocument.guid)
        .outerjoin(mark_seal, mark_seal.c.doc_guid == OneCDocument.guid)
        .outerjoin(mark_ver, mark_ver.c.doc_guid == OneCDocument.guid)
        .where(OneCDocument.is_deleted.is_(False))
    )

    if date_from:
        stmt = stmt.where(OneCDocument.doc_date >= date_from)
    if date_to:
        stmt = stmt.where(OneCDocument.doc_date <= date_to)
    if partner_search:
        stmt = stmt.where(OneCDocument.partner_name.ilike(f"%{partner_search}%"))
    if number_search:
        stmt = stmt.where(
            or_(
                OneCDocument.print_number.ilike(f"%{number_search}%"),
                OneCDocument.number.ilike(f"%{number_search}%"),
            )
        )
    if only_archived:
        stmt = stmt.where(OneCDocument.archive_processed_at.is_not(None))
    if only_without_envelope:
        stmt = stmt.where(EnvelopeDocument.id.is_(None))

    count_stmt = stmt.with_only_columns(func.count(OneCDocument.guid)).order_by(None)
    total: int = (await session.execute(count_stmt)).scalar_one()

    rows = (
        await session.execute(
            stmt.order_by(OneCDocument.doc_date.desc(), OneCDocument.print_number)
            .offset((max(page, 1) - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items: list[dict[str, Any]] = []
    for row in rows:
        doc: OneCDocument = row.OneCDocument
        env: Envelope | None = row.Envelope
        items.append(
            {
                "guid": doc.guid,
                "number": doc.print_number,
                "doc_date": doc.doc_date,
                "doc_type": "УКД" if doc.is_correction else "УПД",
                "partner_name": doc.partner_name,
                "is_edo": doc.is_edo,
                "related_realization_number": doc.related_realization_number,
                "registered_at": row.registered_at,
                "sealed_at": env.sealed_at if env else None,
                "envelope_number": env.number if env else None,
                "origin_branch": row.origin_branch_name,
                "created_by": env.created_by if env else None,
                "verified_at": env.verified_at if env else None,
                "verified_by": env.verified_by if env else None,
                "destination_branch": row.dest_branch_name,
                "has_discrepancy": (
                    env.status == EnvelopeStatus.verified_with_discrepancy
                    if env
                    else False
                ),
                "mark_registered_at": row.mark_reg,
                "mark_sealed_at": row.mark_seal,
                "mark_verified_at": row.mark_ver,
                "archive_processed_at": doc.archive_processed_at,
                "archive_storage_path": doc.archive_storage_path,
                "archive_download_url": doc.archive_download_url,
            }
        )
    return items, total


def build_report_documents_csv(items: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Тип",
            "Номер",
            "Дата",
            "Клиент",
            "ЭДО",
            "Зарегистрирован",
            "Конверт",
            "Запечатан",
            "Отправитель",
            "Оператор",
            "Проверен",
            "Получатель",
            "Расхождение",
            "Отм.1С рег",
            "Отм.1С печать",
            "Отм.1С верифик.",
            "ТехноАрхив дата",
            "ТехноАрхив путь",
            "ТехноАрхив URL",
        ]
    )

    def fmt(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, bool):
            return "Да" if value else ""
        return str(value)

    for row in items:
        writer.writerow(
            [
                fmt(row.get("doc_type")),
                fmt(row.get("number")),
                fmt(row.get("doc_date")),
                fmt(row.get("partner_name")),
                fmt(row.get("is_edo")),
                fmt(row.get("registered_at")),
                fmt(row.get("envelope_number")),
                fmt(row.get("sealed_at")),
                fmt(row.get("origin_branch")),
                fmt(row.get("created_by")),
                fmt(row.get("verified_at")),
                fmt(row.get("destination_branch")),
                fmt(row.get("has_discrepancy")),
                fmt(row.get("mark_registered_at")),
                fmt(row.get("mark_sealed_at")),
                fmt(row.get("mark_verified_at")),
                fmt(row.get("archive_processed_at")),
                fmt(row.get("archive_storage_path")),
                fmt(row.get("archive_download_url")),
            ]
        )
    return output.getvalue()
