import asyncio
import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OneCDocument, SystemSetting
from app.services.odata import OneCClient, parse_odata_date

log = logging.getLogger(__name__)

PAGE_SIZE = 1000
SYNC_STATUS_KEY = "onec_sync_status"

_sync_lock = asyncio.Lock()


def _parse_invoice_row(row: dict[str, Any]) -> dict[str, Any]:
    guid_raw = row.get("Ref_Key")
    if not guid_raw:
        raise ValueError("missing Ref_Key")

    number = str(row.get("Number", ""))
    if not number:
        raise ValueError("missing Number")

    partner_obj = row.get("Партнер")
    partner_name: str | None = None
    if isinstance(partner_obj, dict):
        raw = partner_obj.get("НаименованиеПолное")
        partner_name = str(raw).strip() if raw else None
        partner_name = partner_name or None

    return {
        "guid": uuid.UUID(str(guid_raw)),
        "number": number,
        "print_number": str(row.get("ПредставлениеНомера") or row.get("Number", "")),
        "doc_date": parse_odata_date(row.get("Date")),
        "is_correction": bool(row.get("Корректировочный", False)),
        "partner_name": partner_name,
        "is_edo": bool(row.get("ВыставленВЭлектронномВиде", False)),
        "related_realization_number": None,  # resolved lazily when added to envelope
        "kzv_copy_link": row.get("kzvСсылкаНаКопию") or None,
        "is_deleted": bool(row.get("DeletionMark", False)),
        "last_synced_at": datetime.now(UTC),
    }


async def _upsert_batch(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = pg_insert(OneCDocument).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["guid"],
        set_={
            "number": stmt.excluded.number,
            "print_number": stmt.excluded.print_number,
            "doc_date": stmt.excluded.doc_date,
            "is_correction": stmt.excluded.is_correction,
            "partner_name": stmt.excluded.partner_name,
            "is_edo": stmt.excluded.is_edo,
            "kzv_copy_link": stmt.excluded.kzv_copy_link,
            "is_deleted": stmt.excluded.is_deleted,
            "last_synced_at": stmt.excluded.last_synced_at,
        },
    )
    await session.execute(stmt)


async def _set_sync_status(session: AsyncSession, status: dict[str, Any]) -> None:
    stmt = pg_insert(SystemSetting).values(key=SYNC_STATUS_KEY, value=status)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": stmt.excluded.value}
    )
    await session.execute(stmt)


async def get_sync_status(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(SystemSetting, SYNC_STATUS_KEY)
    return row.value if row else {"state": "never_run"}


async def run_initial_sync(
    client: OneCClient, session: AsyncSession, date_from: date
) -> None:
    await _set_sync_status(
        session,
        {
            "state": "running",
            "mode": "initial",
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    await session.commit()
    total = 0
    errors = 0
    skip = 0
    try:
        while True:
            rows = await client.fetch_invoices_page(
                date_from=date_from,
                date_to=None,
                skip=skip,
                top=PAGE_SIZE,
            )
            if not rows:
                break
            parsed: list[dict[str, Any]] = []
            for row in rows:
                try:
                    parsed.append(_parse_invoice_row(row))
                except Exception:
                    ref_key = row.get("Ref_Key", "<unknown>")
                    log.exception("skip malformed invoice row: Ref_Key=%s", ref_key)
                    errors += 1
            await _upsert_batch(session, parsed)
            await session.commit()
            total += len(parsed)
            skip += PAGE_SIZE
            log.info("initial sync: page done, total=%d", total)
            if len(rows) < PAGE_SIZE:
                break
        await _set_sync_status(
            session,
            {
                "state": "done",
                "mode": "initial",
                "finished_at": datetime.now(UTC).isoformat(),
                "total": total,
                "errors": errors,
            },
        )
        await session.commit()
        log.info("initial sync complete: %d rows, %d errors", total, errors)
    except Exception as e:
        await _set_sync_status(
            session, {"state": "error", "mode": "initial", "error": str(e)}
        )
        await session.commit()
        raise


async def run_incremental_sync(
    client: OneCClient, session: AsyncSession
) -> None:
    restriction_date = await client.get_change_restriction_date()
    if restriction_date is None:
        log.warning("incremental sync: no change restriction date, skipping")
        return

    await _set_sync_status(
        session,
        {
            "state": "running",
            "mode": "incremental",
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    await session.commit()

    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    skip = 0
    total = 0
    errors = 0
    try:
        while True:
            rows = await client.fetch_invoices_page(
                date_from=restriction_date,
                date_to=today,
                skip=skip,
                top=PAGE_SIZE,
                include_deleted=True,
            )
            if not rows:
                break
            parsed: list[dict[str, Any]] = []
            for row in rows:
                try:
                    parsed.append(_parse_invoice_row(row))
                except Exception:
                    ref_key = row.get("Ref_Key", "<unknown>")
                    log.exception("skip malformed invoice row: Ref_Key=%s", ref_key)
                    errors += 1
            await _upsert_batch(session, parsed)
            await session.commit()
            total += len(parsed)
            skip += PAGE_SIZE
            if len(rows) < PAGE_SIZE:
                break
        await _set_sync_status(
            session,
            {
                "state": "done",
                "mode": "incremental",
                "finished_at": datetime.now(UTC).isoformat(),
                "total": total,
                "errors": errors,
            },
        )
        await session.commit()
        log.info("incremental sync complete: %d rows from %s, %d errors", total, restriction_date, errors)
    except Exception as e:
        await _set_sync_status(
            session, {"state": "error", "mode": "incremental", "error": str(e)}
        )
        await session.commit()
        raise
