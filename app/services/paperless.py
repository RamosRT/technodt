import logging
import re
from datetime import UTC, date, datetime
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
_DATE_RE = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{4})(?!\d)")


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


def _extract_date_from_name(name: str | None) -> date | None:
    if not name:
        return None
    m = _DATE_RE.search(name)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def resolve_paperless_doc_date(
    *,
    doc_date_str: str | None,
    file_name: str | None,
    original_filename: str | None,
) -> datetime | None:
    """Prefer DD.MM.YYYY from the invoice filename over Paperless upload timestamp."""
    for name in (file_name, original_filename):
        extracted = _extract_date_from_name(name)
        if extracted is not None:
            return datetime.combine(extracted, datetime.min.time())
    if not doc_date_str:
        return None
    try:
        return datetime.fromisoformat(doc_date_str.replace("Z", "+00:00"))
    except ValueError:
        log.warning("cannot parse paperless date: %r", doc_date_str)
        return None


async def find_matching_document(
    session: AsyncSession,
    *,
    doc_date: datetime | None,
    doc_number: str | None,
) -> OneCDocument | None:
    """Match Paperless invoice to local 1C mirror by document date and number only."""
    if not doc_number or not doc_date:
        return None

    conditions: list = [OneCDocument.is_deleted.is_(False)]

    conditions.append(
        OneCDocument.doc_date == doc_date.date() if hasattr(doc_date, "date") else doc_date
    )

    digits_only = re.sub(r"[^\d]", "", doc_number)
    number_cond = or_(
        OneCDocument.print_number.ilike(f"%{doc_number}%"),
        OneCDocument.number.ilike(f"%{doc_number}%"),
    )
    if digits_only:
        number_cond = or_(
            number_cond,
            OneCDocument.print_number.ilike(f"%{digits_only}%"),
            OneCDocument.number.ilike(f"%{digits_only}%"),
        )
    conditions.append(number_cond)

    stmt = select(OneCDocument).where(and_(*conditions)).limit(5)
    rows = (await session.execute(stmt)).scalars().all()

    if not rows:
        return None

    normalized_number = doc_number.strip().casefold()
    exact = [
        row for row in rows if row.print_number.strip().casefold() == normalized_number
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        log.warning(
            "ambiguous Paperless match: %d rows with exact print_number=%s date=%s",
            len(exact),
            doc_number,
            doc_date,
        )
        return None

    if len(rows) == 1:
        return rows[0]

    log.warning(
        "ambiguous Paperless match: %d candidates for number=%s date=%s",
        len(rows),
        doc_number,
        doc_date,
    )
    return None


async def process_paperless_event(
    session: AsyncSession,
    client: OneCClient,
    *,
    doc_type: str | None,
    doc_date_str: str | None,
    file_name: str | None,
    original_filename: str | None,
    archive_path: str | None,   # DOCUMENT_ARCHIVE_PATH — UNC path to the file
    download_url: str | None,   # DOCUMENT_DOWNLOAD_URL — HTTP link in Paperless
    raise_on_patch_error: bool = False,
    correspondent: str | None = None,  # accepted for API compat; not used in matching
) -> dict[str, Any]:
    if not _is_invoice_type(doc_type):
        return {"status": "skipped", "reason": f"not an invoice type: {doc_type!r}"}

    doc_date = resolve_paperless_doc_date(
        doc_date_str=doc_date_str,
        file_name=file_name,
        original_filename=original_filename,
    )

    doc_number: str | None = None
    for name in (file_name, original_filename):
        if name:
            doc_number = _extract_number_from_name(name)
            if doc_number:
                break

    if doc_date is None:
        return {
            "status": "not_matched",
            "reason": "no_doc_date",
            "doc_number": doc_number,
            "doc_date": doc_date_str,
        }
    if not doc_number:
        return {
            "status": "not_matched",
            "reason": "no_doc_number",
            "doc_date": doc_date_str,
        }

    match = await find_matching_document(
        session,
        doc_date=doc_date,
        doc_number=doc_number,
    )
    if match is None:
        return {
            "status": "not_matched",
            "reason": "no_mirror_match",
            "doc_number": doc_number,
            "doc_date": doc_date.date().isoformat() if hasattr(doc_date, "date") else doc_date_str,
        }

    onec_link = (archive_path or "").strip()
    if not onec_link:
        return {
            "status": "no_storage_path",
            "reason": "archive_path missing",
            "doc_number": doc_number,
            "guid": str(match.guid),
            "print_number": match.print_number,
        }

    now = datetime.now(UTC)

    await session.execute(
        update(OneCDocument)
        .where(OneCDocument.guid == match.guid)
        .values(
            archive_processed_at=now,
            archive_storage_path=archive_path or None,
            archive_download_url=download_url or None,
            kzv_copy_link=onec_link,
        )
    )
    await session.commit()

    try:
        await client.patch_storage_link(
            match.guid, "Document_СчетФактураВыданный", onec_link
        )
    except Exception as exc:
        log.warning("failed to patch 1C storage link for %s: %s", match.guid, exc)
        if raise_on_patch_error:
            raise
        return {
            "status": "onec_patch_failed",
            "reason": str(exc),
            "guid": str(match.guid),
            "print_number": match.print_number,
        }

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
            archive_path=ev.get("archive_path"),
            download_url=ev.get("download_url"),
            correspondent=ev.get("correspondent"),
        )
        results.append({"input": ev, "result": result})
    return results
