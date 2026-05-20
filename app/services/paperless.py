import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OneCDocument
from app.services.odata import OneCClient

log = logging.getLogger(__name__)

# Paperless document type names (as configured in the classifier) that map to invoices.
# "Доверенность" and anything else is skipped.
_INVOICE_TYPES = frozenset({"упд", "укд", "упд/укд"})

# Extracts document number from filenames like "02.03.2026 УПД № УТ-1566 ООО Камский Бекон.pdf"
_NUMBER_RE = re.compile(r"[№#]\s*([\w\-/]+)", re.IGNORECASE)


def _is_invoice_type(doc_type: str | None) -> bool:
    """Returns True only for known invoice types; False for Доверенность or unknown."""
    if not doc_type:
        return False
    normalized = doc_type.strip().lower()
    # If Paperless passes a numeric type ID instead of name — skip (we have no mapping)
    if normalized.isdigit():
        return False
    return normalized in _INVOICE_TYPES


def _extract_number_from_name(name: str) -> str | None:
    m = _NUMBER_RE.search(name)
    return m.group(1).strip() if m else None


async def find_matching_document(
    session: AsyncSession,
    *,
    doc_date: datetime | None,
    doc_number: str | None,
    correspondent: str | None,
) -> OneCDocument | None:
    if not doc_number and not doc_date:
        return None

    conditions: list = [OneCDocument.is_deleted.is_(False)]

    if doc_date:
        # Compare date part only — DOCUMENT_CREATED may include time component
        conditions.append(OneCDocument.doc_date == doc_date.date() if hasattr(doc_date, "date") else doc_date)

    if doc_number:
        # Try exact and suffix match (e.g. "УТ-1566" or just "1566")
        digits_only = re.sub(r"[^\d]", "", doc_number)
        number_cond = or_(
            OneCDocument.print_number.ilike(f"%{doc_number}%"),
            OneCDocument.number.ilike(f"%{doc_number}%"),
        )
        if digits_only:
            number_cond = or_(
                number_cond,
                OneCDocument.print_number.ilike(f"%{digits_only}%"),
            )
        conditions.append(number_cond)

    if correspondent:
        # Use only first 30 chars to avoid overly specific mismatch
        conditions.append(
            OneCDocument.partner_name.ilike(f"%{correspondent[:30]}%")
        )

    stmt = select(OneCDocument).where(and_(*conditions)).limit(5)
    rows = (await session.execute(stmt)).scalars().all()

    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        log.warning(
            "ambiguous Paperless match: %d candidates for number=%s date=%s",
            len(rows),
            doc_number,
            doc_date,
        )
        return None
    return None


async def process_paperless_event(
    session: AsyncSession,
    client: OneCClient,
    *,
    doc_type: str | None,
    doc_date_str: str | None,
    file_name: str | None,
    original_filename: str | None,
    correspondent: str | None,
    archive_path: str | None,   # DOCUMENT_ARCHIVE_PATH — UNC path to the file
    download_url: str | None,   # DOCUMENT_DOWNLOAD_URL — HTTP link in Paperless
) -> dict[str, Any]:
    if not _is_invoice_type(doc_type):
        return {"status": "skipped", "reason": f"not an invoice type: {doc_type!r}"}

    doc_date: datetime | None = None
    if doc_date_str:
        try:
            doc_date = datetime.fromisoformat(doc_date_str.replace("Z", "+00:00"))
        except ValueError:
            log.warning("cannot parse paperless date: %r", doc_date_str)

    doc_number: str | None = None
    for name in (file_name, original_filename):
        if name:
            doc_number = _extract_number_from_name(name)
            if doc_number:
                break

    match = await find_matching_document(
        session,
        doc_date=doc_date,
        doc_number=doc_number,
        correspondent=correspondent,
    )
    if match is None:
        return {
            "status": "not_matched",
            "doc_number": doc_number,
            "doc_date": doc_date_str,
        }

    now = datetime.now(UTC)
    # archive_path = UNC path (stored as plain text in report, pasted into 1C)
    # download_url = HTTP link (stored separately, shown as clickable link in report)
    onec_link = archive_path or ""  # 1C stores the UNC path as kzvСсылкаНаКопию

    await session.execute(
        update(OneCDocument)
        .where(OneCDocument.guid == match.guid)
        .values(
            archive_processed_at=now,
            archive_storage_path=archive_path or None,
            archive_download_url=download_url or None,
            kzv_copy_link=onec_link or None,
        )
    )
    await session.commit()

    if onec_link:
        try:
            await client.patch_storage_link(
                match.guid, "Document_СчетФактураВыданный", onec_link
            )
        except Exception as exc:
            log.warning("failed to patch 1C storage link for %s: %s", match.guid, exc)

    return {
        "status": "matched",
        "guid": str(match.guid),
        "print_number": match.print_number,
    }


async def process_paperless_batch(
    session: AsyncSession,
    client: OneCClient,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for ev in events:
        result = await process_paperless_event(
            session,
            client,
            doc_type=ev.get("doc_type"),
            doc_date_str=ev.get("created"),
            file_name=ev.get("file_name"),
            original_filename=ev.get("original_filename"),
            correspondent=ev.get("correspondent"),
            archive_path=ev.get("archive_path"),
            download_url=ev.get("download_url"),
        )
        results.append({"input": ev, "result": result})
    return results
