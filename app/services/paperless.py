import logging
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
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
_NON_NAME_CHARS_RE = re.compile(r"[^0-9a-zа-я]+", re.IGNORECASE)

_LEGAL_FORM_TOKENS = frozenset(
    {
        "ооо",
        "ао",
        "пао",
        "зао",
        "оао",
        "ип",
        "нко",
        "ано",
        "фгуп",
        "муп",
        "гуп",
        "кфх",
        "пк",
        "спк",
        "общество",
        "ограниченной",
        "ответственностью",
        "акционерное",
        "закрытое",
        "открытое",
    }
)
_GENERIC_PARTNER_TOKENS = frozenset(
    {
        "с",
        "торговый",
        "торговая",
        "торговое",
        "дом",
        "компания",
        "научно",
        "производственное",
        "производственный",
        "объединение",
        "предприятие",
    }
)
_ABBREVIATIONS = {
    "тд": ("торговый", "дом"),
    "тк": ("торговая", "компания"),
    "нпо": ("научно", "производственное", "объединение"),
    "ук": ("управляющая", "компания"),
}
_PARTNER_ALIASES = {
    # Short Paperless classifier names that cannot be inferred reliably by fuzzy matching.
    "кап": ("казанское", "авиапредприятие"),
}
_PARTNER_MATCH_THRESHOLD = 0.86
_PARTNER_AMBIGUOUS_THRESHOLD = 0.90
_PARTNER_AMBIGUOUS_MARGIN = 0.08


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


def _normalize_partner_name(value: str | None) -> str:
    if not value:
        return ""

    clean = _NON_NAME_CHARS_RE.sub(" ", value.casefold().replace("ё", "е"))
    expanded: list[str] = []
    for token in clean.split():
        expanded.extend(_ABBREVIATIONS.get(token, (token,)))

    filtered = [
        token
        for token in expanded
        if token not in _LEGAL_FORM_TOKENS and token not in _GENERIC_PARTNER_TOKENS
    ]
    normalized = " ".join(filtered)
    return " ".join(_PARTNER_ALIASES.get(normalized, filtered))


def _partner_name_score(paperless_name: str | None, onec_name: str | None) -> float:
    left = _normalize_partner_name(paperless_name)
    right = _normalize_partner_name(onec_name)
    if not left or not right:
        return 0.0
    if left == right or left in right or right in left:
        return 1.0

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))

    return max(token_score, SequenceMatcher(None, left, right).ratio())


def _current_partner_substring_match(paperless_name: str | None, onec_name: str | None) -> bool:
    if not paperless_name or not onec_name:
        return False
    return paperless_name[:30].lower() in onec_name.lower()


async def find_matching_document(
    session: AsyncSession,
    *,
    doc_date: datetime | None,
    doc_number: str | None,
    correspondent: str | None,
) -> OneCDocument | None:
    if not doc_number or not doc_date:
        return None

    conditions: list = [OneCDocument.is_deleted.is_(False)]

    # Compare date part only — DOCUMENT_CREATED may include time component.
    conditions.append(OneCDocument.doc_date == doc_date.date() if hasattr(doc_date, "date") else doc_date)

    # Try exact and suffix match (e.g. "УТ-1566" or just "1566").
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

    scored = sorted(
        ((row, _partner_name_score(correspondent, row.partner_name)) for row in rows),
        key=lambda item: item[1],
        reverse=True,
    )

    if len(scored) == 1:
        row, score = scored[0]
        if not correspondent or score >= _PARTNER_MATCH_THRESHOLD:
            if correspondent and not _current_partner_substring_match(correspondent, row.partner_name):
                log.info(
                    "matched Paperless correspondent via normalized score %.3f: %r -> %r",
                    score,
                    correspondent,
                    row.partner_name,
                )
            return row
        log.warning(
            "Paperless match rejected by correspondent score %.3f for number=%s date=%s: %r -> %r",
            score,
            doc_number,
            doc_date,
            correspondent,
            row.partner_name,
        )
        return None

    best_row, best_score = scored[0]
    second_score = scored[1][1]
    if (
        best_score >= _PARTNER_AMBIGUOUS_THRESHOLD
        and best_score - second_score >= _PARTNER_AMBIGUOUS_MARGIN
    ):
        return best_row

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
    raise_on_patch_error: bool = False,
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
            if raise_on_patch_error:
                raise

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
