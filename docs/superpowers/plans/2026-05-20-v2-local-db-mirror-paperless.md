# Конверт-трек v2.0: Local DB Mirror + Document Report + Paperless Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace constant 1C queries with a local document cache, add a full document report view, and integrate with Paperless (TechnoArchive) via post-consumption webhook.

**Architecture:** A new `onec_documents` table mirrors all `Document_СчетФактураВыданный` from 1C (initial paginated load + APScheduler incremental sync). Document lookups for счет-фактуры use the local cache; перемещения fall back to live 1C. A webhook endpoint accepts Paperless post-consumption events, matches them to local documents by number+date+correspondent, marks archive status, and PATCHes 1C with the storage link. Existing Paperless documents are handled via a batch admin endpoint.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, APScheduler 3.x, PostgreSQL 16, httpx, Pydantic v2

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/models/onec_document.py` | Create | SQLAlchemy model: local 1C invoice mirror |
| `app/models/__init__.py` | Modify | Export `OneCDocument` |
| `alembic/versions/0008_onec_documents.py` | Create | DB migration |
| `app/config.py` | Modify | Add `paperless_webhook_api_key`, sync settings |
| `app/services/odata.py` | Modify | Add bulk fetch, change restriction date, patch storage link |
| `app/services/onec_sync.py` | Create | Initial + incremental sync logic |
| `app/services/report.py` | Create | Document report query |
| `app/services/paperless.py` | Create | Paperless matching + archive marking |
| `app/schemas/report.py` | Create | Pydantic schemas for document report |
| `app/routers/api/onec_sync.py` | Create | Admin: start/status sync |
| `app/routers/api/report.py` | Create | GET /api/report/documents |
| `app/routers/api/webhooks.py` | Create | POST /api/webhooks/paperless |
| `app/main.py` | Modify | Register new routers, setup APScheduler |
| `scripts/paperless_post_consume.sh` | Create | Shell hook for Paperless server |
| `scripts/paperless_bulk_import.py` | Create | Batch import existing Paperless docs via API |

---

## Task 1: OneCDocument model + migration

**Files:**
- Create: `app/models/onec_document.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/0008_onec_documents.py`

- [ ] **Step 1: Write the model**

```python
# app/models/onec_document.py
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OneCDocument(Base):
    __tablename__ = "onec_documents"

    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    print_number: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    partner_name: Mapped[str | None] = mapped_column(String(500))
    is_edo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    related_realization_number: Mapped[str | None] = mapped_column(String(50))
    kzv_copy_link: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    first_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archive_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_storage_path: Mapped[str | None] = mapped_column(Text)  # UNC path e.g. \\server\folder\file.pdf
    archive_download_url: Mapped[str | None] = mapped_column(Text)  # Paperless DOCUMENT_DOWNLOAD_URL
```

- [ ] **Step 2: Add to models __init__.py**

In `app/models/__init__.py` add the import and the export:
```python
from .onec_document import OneCDocument
```
And add `"OneCDocument"` to `__all__`.

- [ ] **Step 3: Write migration**

```python
# alembic/versions/0008_onec_documents.py
"""add onec_documents table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onec_documents",
        sa.Column("guid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("print_number", sa.String(100), nullable=False),
        sa.Column("doc_date", sa.Date, nullable=False),
        sa.Column("is_correction", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("partner_name", sa.String(500)),
        sa.Column("is_edo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("related_realization_number", sa.String(50)),
        sa.Column("kzv_copy_link", sa.Text),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("first_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("archive_processed_at", sa.DateTime(timezone=True)),
        sa.Column("archive_storage_path", sa.Text),
        sa.Column("archive_download_url", sa.Text),
    )
    op.create_index("ix_onec_documents_doc_date", "onec_documents", ["doc_date"])
    op.create_index("ix_onec_documents_print_number", "onec_documents", ["print_number"])
    op.create_index("ix_onec_documents_is_deleted", "onec_documents", ["is_deleted"])


def downgrade() -> None:
    op.drop_table("onec_documents")
```

- [ ] **Step 4: Apply migration**

```bash
venv\Scripts\python -m alembic upgrade head
```

Expected: last line contains `Running upgrade 0007 -> 0008, add onec_documents table`

- [ ] **Step 5: Commit**

```bash
git add app/models/onec_document.py app/models/__init__.py alembic/versions/0008_onec_documents.py
git commit -m "feat: add OneCDocument model and migration 0008"
```

---

## Task 2: Config additions

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Add fields to Settings class**

In `app/config.py`, add these fields inside the `Settings` class (after existing fields):

```python
paperless_webhook_api_key: str = ""
sync_initial_from_date: str = "2023-01-01"
sync_schedule_hours: int = 4
```

- [ ] **Step 2: Verify settings load**

```bash
venv\Scripts\python -c "from app.config import get_settings; s = get_settings(); print(s.sync_schedule_hours, s.sync_initial_from_date)"
```

Expected: `4 2023-01-01`

- [ ] **Step 3: Add PAPERLESS_WEBHOOK_API_KEY to .env.example**

```
PAPERLESS_WEBHOOK_API_KEY=change_me_strong_token
SYNC_INITIAL_FROM_DATE=2023-01-01
SYNC_SCHEDULE_HOURS=4
```

- [ ] **Step 4: Commit**

```bash
git add app/config.py .env.example
git commit -m "feat: add v2.0 config settings (sync schedule, paperless api key)"
```

---

## Task 3: OData client — bulk invoice fetch + patch storage link

**Files:**
- Modify: `app/services/odata.py`

- [ ] **Step 1: Add INVOICE_SYNC_SELECT constant**

After the existing `SELECT_FIELDS` dict in `app/services/odata.py`, add:

```python
INVOICE_SYNC_SELECT = (
    "Ref_Key",
    "Number",
    "ПредставлениеНомера",
    "Date",
    "Корректировочный",
    "DeletionMark",
    "ВыставленВЭлектронномВиде",
    "kzvСсылкаНаКопию",
    "ДокументОснование",
    "ДокументОснование_Type",
)

INVOICE_PARTNER_EXPAND = "Партнер($select=НаименованиеПолное)"
```

- [ ] **Step 2: Add fetch_invoices_page to OneCClient**

Add this method to the `OneCClient` class:

```python
async def fetch_invoices_page(
    self,
    *,
    date_from: date,
    date_to: date | None,
    skip: int,
    top: int,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    filters = [f"Date ge datetime'{date_from.isoformat()}T00:00:00'"]
    if date_to is not None:
        filters.append(f"Date le datetime'{date_to.isoformat()}T23:59:59'")
    if not include_deleted:
        filters.append("DeletionMark eq false")
    params = {
        "$format": "json",
        "$select": ",".join(INVOICE_SYNC_SELECT),
        "$expand": INVOICE_PARTNER_EXPAND,
        "$filter": " and ".join(filters),
        "$skip": str(skip),
        "$top": str(top),
    }
    try:
        resp = await self._client.get("/Document_СчетФактураВыданный", params=params)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
        raise OneCUnavailable("1С недоступна при синхронизации") from e
    if resp.status_code == 401:
        raise OneCUnavailable("Не удалось авторизоваться в 1С")
    if resp.status_code != 200:
        raise OneCUnavailable(f"1С вернула {resp.status_code} при синхронизации")
    data = resp.json()
    return data.get("value", [])
```

- [ ] **Step 3: Add get_change_restriction_date to OneCClient**

```python
async def get_change_restriction_date(self) -> "date | None":
    params = {
        "$format": "json",
        "$select": "ДатаЗапрета",
        "$orderby": "ДатаЗапрета desc",
        "$top": "1",
    }
    try:
        resp = await self._client.get(
            "/InformationRegister_ДатыЗапретаИзменения", params=params
        )
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError):
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    items = data.get("value", [])
    if not items:
        return None
    raw = items[0].get("ДатаЗапрета")
    return _parse_odata_date(raw) if raw else None
```

- [ ] **Step 4: Add patch_storage_link to OneCClient**

```python
async def patch_storage_link(
    self,
    doc_guid: uuid.UUID,
    doc_entity: str,
    storage_link: str,
) -> None:
    url = f"/{doc_entity}(guid'{doc_guid}')"
    body = {"kzvСсылкаНаКопию": storage_link}
    params = {"$format": "json"}
    try:
        resp = await self._client.patch(url, json=body, params=params)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
        raise OneCUnavailable("1С недоступна при патче ссылки") from e
    if resp.status_code not in (200, 204):
        raise OneCUnavailable(f"1С вернула {resp.status_code} при patch storage link")
```

Note: `date` is already imported at the top of `odata.py`. If not, add `from datetime import date`.

- [ ] **Step 5: Commit**

```bash
git add app/services/odata.py
git commit -m "feat: OData bulk invoice fetch, change restriction date, patch storage link"
```

---

## Task 4: OnecSync service

**Files:**
- Create: `app/services/onec_sync.py`

- [ ] **Step 1: Write the service file**

```python
# app/services/onec_sync.py
import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OneCDocument, SystemSetting
from app.services.odata import OneCClient, _parse_odata_date

log = logging.getLogger(__name__)

PAGE_SIZE = 1000
SYNC_STATUS_KEY = "onec_sync_status"


def _parse_invoice_row(row: dict[str, Any]) -> dict[str, Any]:
    guid_raw = row.get("Ref_Key")
    if not guid_raw:
        raise ValueError("missing Ref_Key")

    partner_obj = row.get("Партнер")
    partner_name: str | None = None
    if isinstance(partner_obj, dict):
        raw = partner_obj.get("НаименованиеПолное")
        partner_name = str(raw).strip() if raw else None

    return {
        "guid": uuid.UUID(str(guid_raw)),
        "number": str(row.get("Number", "")),
        "print_number": str(row.get("ПредставлениеНомера") or row.get("Number", "")),
        "doc_date": _parse_odata_date(row.get("Date")),
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
    await session.commit()


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
                except Exception as e:
                    log.warning("skip malformed invoice row: %s", e)
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
        log.info("initial sync complete: %d rows, %d errors", total, errors)
    except Exception as e:
        await _set_sync_status(
            session, {"state": "error", "mode": "initial", "error": str(e)}
        )
        raise


async def run_incremental_sync(
    client: OneCClient, session: AsyncSession
) -> None:
    restriction_date = await client.get_change_restriction_date()
    if restriction_date is None:
        log.warning("incremental sync: no change restriction date, skipping")
        return

    today = datetime.now(UTC).date()
    skip = 0
    total = 0
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
            except Exception as e:
                log.warning("skip malformed row in incremental sync: %s", e)
        await _upsert_batch(session, parsed)
        await session.commit()
        total += len(parsed)
        skip += PAGE_SIZE
        if len(rows) < PAGE_SIZE:
            break

    log.info("incremental sync complete: %d rows from %s", total, restriction_date)
```

- [ ] **Step 2: Verify import works**

```bash
venv\Scripts\python -c "from app.services.onec_sync import run_initial_sync; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/services/onec_sync.py
git commit -m "feat: OnecSync service with initial and incremental sync"
```

---

## Task 5: Admin sync endpoints + APScheduler

**Files:**
- Create: `app/routers/api/onec_sync.py`
- Modify: `app/main.py`

- [ ] **Step 1: Install APScheduler**

In `pyproject.toml` dependencies, add: `"apscheduler>=3.10,<4"`. Then install:

```bash
venv\Scripts\pip install "apscheduler>=3.10,<4"
```

Expected: last line `Successfully installed apscheduler-3.x.x`

- [ ] **Step 2: Write admin sync router**

```python
# app/routers/api/onec_sync.py
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.services.onec_sync import get_sync_status, run_initial_sync, run_incremental_sync
from app.services.odata import OneCClient

router = APIRouter(prefix="/api/admin/sync", tags=["sync"])


@router.get("/status")
async def sync_status(
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    return await get_sync_status(session)


@router.post("/initial")
async def start_initial_sync(
    background_tasks: BackgroundTasks,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
):
    settings = get_settings()
    date_from = date.fromisoformat(settings.sync_initial_from_date)

    async def _run() -> None:
        await run_initial_sync(client, session, date_from)

    background_tasks.add_task(_run)
    return {"status": "started", "date_from": str(date_from)}


@router.post("/incremental")
async def start_incremental_sync(
    background_tasks: BackgroundTasks,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
):
    async def _run() -> None:
        await run_incremental_sync(client, session)

    background_tasks.add_task(_run)
    return {"status": "started"}
```

- [ ] **Step 3: Add APScheduler to lifespan in main.py**

In `app/main.py`, add these imports at the top:

```python
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db import get_session_factory
from app.services.onec_sync import run_incremental_sync
from app.routers.api import onec_sync as onec_sync_api

log = logging.getLogger(__name__)
```

Replace the existing `lifespan` function with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    client = OneCClient(
        base_url=s.odata_base_url,
        user=s.odata_admin_user,
        password=s.odata_password,
        timeout=s.odata_timeout_seconds,
    )
    app.state.one_c = client
    app.dependency_overrides[get_one_c_client] = lambda: app.state.one_c

    scheduler = AsyncIOScheduler()

    async def _scheduled_sync() -> None:
        factory = get_session_factory()
        async with factory() as session:
            try:
                await run_incremental_sync(client, session)
            except Exception as exc:
                log.error("scheduled incremental sync failed: %s", exc)

    if s.sync_schedule_hours > 0:
        scheduler.add_job(
            _scheduled_sync,
            "interval",
            hours=s.sync_schedule_hours,
            id="incremental_sync",
        )

    scheduler.start()
    app.state.scheduler = scheduler

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await client.aclose()
```

Also add `app.include_router(onec_sync_api.router)` after the other `include_router` calls.

- [ ] **Step 4: Start the server and verify no errors**

```bash
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Expected: no ImportError, no startup exception. Press Ctrl+C to stop.

- [ ] **Step 5: Commit**

```bash
git add app/routers/api/onec_sync.py app/main.py
git commit -m "feat: admin sync endpoints and APScheduler incremental sync"
```

---

## Task 6: Document lookup via local DB cache

**Files:**
- Modify: `app/services/envelopes.py`

The goal: when adding a document to an envelope, if the GUID is found in `onec_documents`, use local data instead of calling 1C (счет-фактуры only; перемещения still go to 1C).

- [ ] **Step 1: Add local DB lookup helper to envelopes.py**

At the top of `app/services/envelopes.py`, add import:
```python
from app.models import OneCDocument
```

Add this function before `add_document_to_envelope` (find the exact function name with `grep -n "lookup_document_with_related" app/services/envelopes.py`):

```python
async def _lookup_from_local_cache(
    session: AsyncSession, guid: uuid.UUID
) -> "NormalizedDocument | None":
    from app.services.odata import NormalizedDocument
    doc = await session.get(OneCDocument, guid)
    if doc is None or doc.is_deleted:
        return None
    return NormalizedDocument(
        entity="Document_СчетФактураВыданный",
        doc_kind="УКД" if doc.is_correction else "УПД",
        doc_number=doc.print_number,
        doc_date=doc.doc_date,
        related_realization_ref=None,
        raw_payload={},
        partner_name=doc.partner_name,
        related_realization_number=doc.related_realization_number,
    )
```

- [ ] **Step 2: Find where lookup_document_with_related is called**

Run:
```bash
venv\Scripts\python -m grep -rn "lookup_document_with_related" app\services\envelopes.py
```

Identify the exact line. It will look like:
```python
normalized = await client.lookup_document_with_related(doc_guid)
```

- [ ] **Step 3: Replace the live 1C call with cache-first lookup**

Replace that single line with:
```python
normalized = await _lookup_from_local_cache(session, doc_guid)
if normalized is None:
    normalized = await client.lookup_document_with_related(doc_guid)
```

(The session parameter must already be in scope for this function — it is, since all service functions take `session: AsyncSession`.)

- [ ] **Step 4: Also update partner_name in local DB when resolved from 1C**

Directly after the `lookup_document_with_related` call (inside `if normalized is None` block), add:

```python
# Backfill partner_name into local cache if this is a счет-фактура
if normalized.entity == "Document_СчетФактураВыданный" and normalized.partner_name:
    from sqlalchemy import update
    await session.execute(
        update(OneCDocument)
        .where(OneCDocument.guid == doc_guid)
        .values(partner_name=normalized.partner_name)
    )
```

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py
git commit -m "feat: use local OneCDocument cache for invoice lookups, fallback to 1C"
```

---

## Task 7: Document report API

**Files:**
- Create: `app/schemas/report.py`
- Create: `app/services/report.py`
- Create: `app/routers/api/report.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write report Pydantic schemas**

```python
# app/schemas/report.py
import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class ReportDocumentRow(BaseModel):
    guid: uuid.UUID
    number: str
    doc_date: date
    doc_type: str
    partner_name: Optional[str] = None
    is_edo: bool
    related_realization_number: Optional[str] = None
    registered_at: Optional[datetime] = None
    sealed_at: Optional[datetime] = None
    envelope_number: Optional[str] = None
    origin_branch: Optional[str] = None
    created_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    destination_branch: Optional[str] = None
    has_discrepancy: bool = False
    mark_registered_at: Optional[datetime] = None
    mark_sealed_at: Optional[datetime] = None
    mark_verified_at: Optional[datetime] = None
    archive_processed_at: Optional[datetime] = None
    archive_storage_path: Optional[str] = None   # UNC path, shown as plain text
    archive_download_url: Optional[str] = None   # clickable HTTP(S) link from Paperless

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    items: list[ReportDocumentRow]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: Write report service**

```python
# app/services/report.py
import uuid
from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Branch, Envelope, EnvelopeDocument, EnvelopeStatus, OneCDocument, OneCMarkLog
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
                    OneCMarkLog.status == "ok",
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
        env_doc: EnvelopeDocument | None = row.EnvelopeDocument
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
```

- [ ] **Step 3: Write report router**

```python
# app/routers/api/report.py
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.report import ReportDocumentRow, ReportResponse
from app.services.report import list_report_documents

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/documents", response_model=ReportResponse)
async def documents_report(
    _op: str = require_operator(),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    partner: Optional[str] = Query(None),
    number: Optional[str] = Query(None),
    only_archived: bool = Query(False),
    only_without_envelope: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    items, total = await list_report_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        partner_search=partner,
        number_search=number,
        only_archived=only_archived,
        only_without_envelope=only_without_envelope,
        page=page,
        page_size=page_size,
    )
    return ReportResponse(
        items=[ReportDocumentRow(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 4: Register in main.py**

In `app/main.py` add:
```python
from app.routers.api import report as report_api
# ...
app.include_router(report_api.router)
```

- [ ] **Step 5: Smoke test the endpoint**

Start server, then:
```bash
curl -s "http://127.0.0.1:8080/api/report/documents?page_size=5" | python -m json.tool
```
Expected: JSON with `{"items": [...], "total": <number>, "page": 1, "page_size": 5}`

- [ ] **Step 6: Commit**

```bash
git add app/schemas/report.py app/services/report.py app/routers/api/report.py app/main.py
git commit -m "feat: document report API (/api/report/documents)"
```

---

## Task 8: Paperless integration service + webhook

**Files:**
- Create: `app/services/paperless.py`
- Create: `app/routers/api/webhooks.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write Paperless matching service**

```python
# app/services/paperless.py
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
_SKIP_TYPES = frozenset({"доверенность"})

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


class BatchEventItem:
    """Mirrors PaperlessEvent — used by the batch endpoint."""
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


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
```

- [ ] **Step 2: Write webhook router**

```python
# app/routers/api/webhooks.py
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.services.odata import OneCClient
from app.services.paperless import process_paperless_batch, process_paperless_event

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _check_api_key(authorization: str = Header(default="")) -> None:
    key = get_settings().paperless_webhook_api_key
    if not key:
        return  # disabled when not configured
    token = authorization.removeprefix("Bearer ").strip()
    if token != key:
        raise HTTPException(status_code=401, detail="Invalid API key")


class PaperlessEvent(BaseModel):
    document_id: Optional[int] = None
    file_name: Optional[str] = None
    doc_type: Optional[str] = None
    created: Optional[str] = None
    correspondent: Optional[str] = None
    download_url: Optional[str] = None
    source_path: Optional[str] = None
    archive_path: Optional[str] = None
    original_filename: Optional[str] = None
    tags: Optional[str] = None


@router.post("/paperless")
async def paperless_post_consume(
    event: PaperlessEvent,
    _: None = Depends(_check_api_key),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
) -> dict[str, Any]:
    return await process_paperless_event(
        session,
        client,
        doc_type=event.doc_type,
        doc_date_str=event.created,
        file_name=event.file_name,
        original_filename=event.original_filename,
        correspondent=event.correspondent,
        archive_path=event.archive_path,
        download_url=event.download_url,
    )


@router.post("/paperless/batch")
async def paperless_batch(
    events: list[PaperlessEvent],
    _: None = Depends(_check_api_key),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
) -> list[dict[str, Any]]:
    return await process_paperless_batch(
        session, client, [ev.model_dump() for ev in events]
    )
```

- [ ] **Step 3: Register webhook router in main.py**

In `app/main.py` add:
```python
from app.routers.api import webhooks as webhooks_api
# ...
app.include_router(webhooks_api.router)
```

- [ ] **Step 4: Smoke test the webhook**

Start server, then:
```bash
curl -s -X POST http://127.0.0.1:8080/api/webhooks/paperless \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d "{\"doc_type\": \"доверенность\", \"created\": \"2026-01-01\"}"
```
Expected: `{"status":"skipped","reason":"not an invoice type: 'доверенность'"}`

- [ ] **Step 5: Commit**

```bash
git add app/services/paperless.py app/routers/api/webhooks.py app/main.py
git commit -m "feat: Paperless post-consumption webhook, matching service, batch endpoint"
```

---

## Task 9: Paperless post-consume shell script

**Files:**
- Create: `scripts/paperless_post_consume.sh`

- [ ] **Step 1: Create scripts directory and write script**

```bash
mkdir scripts
```

```bash
#!/usr/bin/env bash
# Paperless-ngx post-consumption hook for Конверт-трек.
# Deploy on the Paperless server. Set in paperless.conf:
#   PAPERLESS_POST_CONSUME_SCRIPT=/opt/scripts/konvertrek_post_consume.sh
# Set environment variables:
#   KONVERTREK_URL=http://10.60.6.11:8080
#   KONVERTREK_API_KEY=<value from .env PAPERLESS_WEBHOOK_API_KEY>

set -euo pipefail

KONVERTREK_URL="${KONVERTREK_URL:-http://10.60.6.11:8080}"
KONVERTREK_API_KEY="${KONVERTREK_API_KEY:-}"

# Build JSON payload from Paperless env vars (always present after consumption)
payload=$(printf '{
  "document_id": %s,
  "file_name": %s,
  "doc_type": %s,
  "created": %s,
  "correspondent": %s,
  "download_url": %s,
  "source_path": %s,
  "original_filename": %s
}' \
  "${DOCUMENT_ID:-0}" \
  "\"${DOCUMENT_FILE_NAME:-}\"" \
  "\"${DOCUMENT_TYPE:-}\"" \
  "\"${DOCUMENT_CREATED:-}\"" \
  "\"${DOCUMENT_CORRESPONDENT:-}\"" \
  "\"${DOCUMENT_DOWNLOAD_URL:-}\"" \
  "\"${DOCUMENT_SOURCE_PATH:-}\"" \
  "\"${DOCUMENT_ORIGINAL_FILENAME:-}\""
)

curl -sf \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${KONVERTREK_API_KEY}" \
  --data "$payload" \
  "${KONVERTREK_URL}/api/webhooks/paperless" \
  || echo "[konvertrek] webhook call failed (non-fatal)" >&2

exit 0
```

Save as `scripts/paperless_post_consume.sh`.

- [ ] **Step 2: Deployment notes (add as comments in the script header)**

On the Paperless Linux server:
```bash
chmod +x /opt/scripts/konvertrek_post_consume.sh
```
In `/etc/paperless.conf` or `docker-compose.env`:
```
PAPERLESS_POST_CONSUME_SCRIPT=/opt/scripts/konvertrek_post_consume.sh
KONVERTREK_URL=http://10.60.6.11:8080
KONVERTREK_API_KEY=<same value as .env PAPERLESS_WEBHOOK_API_KEY>
```

For **existing** Paperless documents (десятки тысяч): export a JSON list of document metadata from Paperless DB and POST to `POST /api/webhooks/paperless/batch`. Example batch item shape: same as `PaperlessEvent`.

- [ ] **Step 3: Commit**

```bash
git add scripts/paperless_post_consume.sh
git commit -m "feat: add Paperless post-consume shell script"
```

---

## Task 10: UI — document report page

**Files:**
- Modify: `app/web/static/index.html` (check actual path with `dir app\web\static\`)

The report section needs filters, a table with all columns, and pagination.

- [x] **Step 1: Confirm HTML file path**

```bash
dir app\web\static\
```

Identify the `.html` file (likely `index.html`).

- [x] **Step 2: Add report tab navigation button**

In the existing navigation/tab area, add a button alongside the other main actions:

```html
<button id="btn-nav-report" class="nav-btn">Отчёт по документам</button>
```

In the JS, add a click handler to switch to the report section (follow the existing section-switching pattern in the file).

- [x] **Step 3: Add report section HTML**

After the existing main sections, add:

```html
<section id="section-report" class="hidden">
  <div class="filter-bar">
    <label>Дата с: <input type="date" id="rep-date-from"></label>
    <label>Дата по: <input type="date" id="rep-date-to"></label>
    <input type="text" id="rep-number" placeholder="Номер документа" style="width:14em">
    <input type="text" id="rep-partner" placeholder="Клиент" style="width:14em">
    <label><input type="checkbox" id="rep-archived"> Только в ТехноАрхиве</label>
    <label><input type="checkbox" id="rep-no-envelope"> Без конверта</label>
    <button id="btn-rep-search">Найти</button>
    <button id="btn-rep-csv">CSV</button>
  </div>
  <div id="rep-total" style="padding:4px 0;font-size:.9em;color:#555"></div>
  <div style="overflow-x:auto">
    <table id="rep-table" class="doc-table">
      <thead><tr>
        <th>Тип</th><th>Номер</th><th>Дата</th><th>Клиент</th>
        <th>ЭДО</th><th>Зарегистрирован</th><th>Конверт</th>
        <th>Запечатан</th><th>Отправитель</th><th>Оператор</th>
        <th>Проверен</th><th>Получатель</th><th>Расх.</th>
        <th>Отм.1С рег</th><th>Отм.1С печать</th><th>Отм.1С верифик.</th>
        <th>ТехноАрхив</th>
      </tr></thead>
      <tbody id="rep-body"></tbody>
    </table>
  </div>
  <div id="rep-pager"></div>
</section>
```

- [x] **Step 4: Add JS for report fetch and render**

In the `<script>` block add:

```javascript
let repPage = 1;

function repParams() {
  const p = new URLSearchParams({ page: repPage, page_size: 50 });
  const v = (id) => document.getElementById(id).value;
  const c = (id) => document.getElementById(id).checked;
  if (v('rep-date-from')) p.set('date_from', v('rep-date-from'));
  if (v('rep-date-to'))   p.set('date_to',   v('rep-date-to'));
  if (v('rep-number').trim()) p.set('number', v('rep-number').trim());
  if (v('rep-partner').trim()) p.set('partner', v('rep-partner').trim());
  if (c('rep-archived'))    p.set('only_archived', 'true');
  if (c('rep-no-envelope')) p.set('only_without_envelope', 'true');
  return p;
}

async function loadReport() {
  const resp = await fetch(`/api/report/documents?${repParams()}`);
  if (!resp.ok) { console.error('report fetch failed', resp.status); return; }
  const data = await resp.json();
  document.getElementById('rep-total').textContent = `Всего: ${data.total}`;
  const tbody = document.getElementById('rep-body');
  tbody.innerHTML = '';
  for (const r of data.items) {
    const tr = document.createElement('tr');
    const d = (v) => v ? v.slice(0, 10) : '';
    tr.innerHTML = `
      <td>${r.doc_type}</td>
      <td>${r.number}</td>
      <td>${d(r.doc_date)}</td>
      <td>${r.partner_name || ''}</td>
      <td>${r.is_edo ? 'Да' : ''}</td>
      <td>${d(r.registered_at)}</td>
      <td>${r.envelope_number || ''}</td>
      <td>${d(r.sealed_at)}</td>
      <td>${r.origin_branch || ''}</td>
      <td>${r.created_by || ''}</td>
      <td>${d(r.verified_at)}</td>
      <td>${r.destination_branch || ''}</td>
      <td>${r.has_discrepancy ? '⚠' : ''}</td>
      <td>${d(r.mark_registered_at)}</td>
      <td>${d(r.mark_sealed_at)}</td>
      <td>${d(r.mark_verified_at)}</td>
      <td>${r.archive_processed_at
            ? (r.archive_download_url
                ? `<a href="${r.archive_download_url}" target="_blank">✓ ${d(r.archive_processed_at)}</a>`
                : `✓ ${d(r.archive_processed_at)}`)
            : ''}</td>
    `;
    tbody.appendChild(tr);
  }
  // Pagination
  const pages = Math.ceil(data.total / 50);
  const pager = document.getElementById('rep-pager');
  pager.innerHTML = '';
  if (repPage > 1) {
    const b = document.createElement('button');
    b.textContent = '← Назад';
    b.onclick = () => { repPage--; loadReport(); };
    pager.appendChild(b);
  }
  if (pages > 1) {
    pager.appendChild(document.createTextNode(` Стр. ${repPage}/${pages} `));
  }
  if (repPage < pages) {
    const b = document.createElement('button');
    b.textContent = 'Далее →';
    b.onclick = () => { repPage++; loadReport(); };
    pager.appendChild(b);
  }
}

document.getElementById('btn-rep-search').addEventListener('click', () => {
  repPage = 1; loadReport();
});

// CSV export via existing pattern (download as file)
document.getElementById('btn-rep-csv').addEventListener('click', async () => {
  const p = repParams();
  p.set('page_size', '10000');
  window.location = `/api/report/documents?${p}&format=csv`;
});

// Tab switching — add alongside other section switches in existing code
document.getElementById('btn-nav-report').addEventListener('click', () => {
  showSection('section-report');
  loadReport();
});
```

Note: `showSection` should be the existing helper in the code that hides other sections. Match the name used in the file.

- [x] **Step 5: Test in browser**

Start server, open `http://127.0.0.1:8080`, click "Отчёт по документам", verify table loads (will be empty until initial sync runs).

- [ ] **Step 6: Commit**

```bash
git add app/web/static/
git commit -m "feat: document report UI page with filters and pagination"
```

---

---

## Task 11: Batch import of existing Paperless documents

**Files:**
- Create: `scripts/paperless_bulk_import.py`

This script calls the Paperless REST API, paginates through all existing documents, filters by invoice types, and sends them in batches to our `POST /api/webhooks/paperless/batch` endpoint. Run once manually after deployment to backfill all existing documents.

- [x] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""
One-shot script: imports existing Paperless documents into Конверт-трек.

Usage:
    python scripts/paperless_bulk_import.py \
        --paperless-url http://paperless-host:8000 \
        --paperless-token <PAPERLESS_API_TOKEN> \
        --konvertrek-url http://10.60.6.11:8080 \
        --konvertrek-key <PAPERLESS_WEBHOOK_API_KEY>
"""
import argparse
import sys
import time
from typing import Any

import httpx

INVOICE_TYPES = {"упд", "укд", "упд/укд"}
BATCH_SIZE = 50


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--paperless-url", required=True)
    p.add_argument("--paperless-token", required=True)
    p.add_argument("--konvertrek-url", required=True)
    p.add_argument("--konvertrek-key", required=True)
    p.add_argument("--dry-run", action="store_true", help="fetch only, do not send")
    return p.parse_args()


def is_invoice(doc: dict[str, Any], type_map: dict[int, str]) -> bool:
    type_id = doc.get("document_type")
    if type_id is None:
        return False
    type_name = type_map.get(type_id, "").strip().lower()
    return type_name in INVOICE_TYPES


def fetch_document_types(client: httpx.Client) -> dict[int, str]:
    resp = client.get("/api/document_types/?page_size=100")
    resp.raise_for_status()
    return {t["id"]: t["name"] for t in resp.json().get("results", [])}


def fetch_documents_page(client: httpx.Client, page: int) -> dict[str, Any]:
    resp = client.get(f"/api/documents/?page={page}&page_size=100&ordering=-created")
    resp.raise_for_status()
    return resp.json()


def build_event(doc: dict[str, Any], type_map: dict[int, str]) -> dict[str, Any]:
    type_id = doc.get("document_type")
    return {
        "document_id": doc.get("id"),
        "file_name": doc.get("title", ""),
        "doc_type": type_map.get(type_id, "") if type_id else "",
        "created": doc.get("created", ""),
        "correspondent": doc.get("correspondent_name", "") or "",
        "download_url": doc.get("__download_url", ""),
        "original_filename": doc.get("original_file_name", ""),
        "archive_path": "",  # not exposed in Paperless list API
    }


def send_batch(
    kr_client: httpx.Client,
    kr_key: str,
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resp = kr_client.post(
        "/api/webhooks/paperless/batch",
        json=batch,
        headers={"Authorization": f"Bearer {kr_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    args = parse_args()

    pl_client = httpx.Client(
        base_url=args.paperless_url,
        headers={"Authorization": f"Token {args.paperless_token}"},
        timeout=30,
    )
    kr_client = httpx.Client(base_url=args.konvertrek_url, timeout=60)

    print("Fetching Paperless document types...")
    type_map = fetch_document_types(pl_client)
    print(f"  Found {len(type_map)} types: {type_map}")

    page = 1
    total_fetched = 0
    total_matched = 0
    total_sent = 0
    batch: list[dict[str, Any]] = []

    while True:
        data = fetch_documents_page(pl_client, page)
        docs = data.get("results", [])
        if not docs:
            break

        # Enrich correspondent name (list API returns ID, not name)
        # Paperless API returns correspondent as int ID; fetch name via separate call if needed.
        # Simpler: correspondent is in doc["correspondent"] as ID, name in doc["__correspondent__"]
        for doc in docs:
            if is_invoice(doc, type_map):
                # Build download URL from doc ID
                doc["__download_url"] = f"{args.paperless_url}/api/documents/{doc['id']}/download/"
                # Correspondent name: Paperless returns it as 'correspondent' (ID) but
                # the search endpoint includes correspondent_name — check your Paperless version
                doc["correspondent_name"] = doc.get("correspondent_name") or ""
                event = build_event(doc, type_map)
                batch.append(event)
                total_matched += 1

        total_fetched += len(docs)

        if len(batch) >= BATCH_SIZE:
            if not args.dry_run:
                results = send_batch(kr_client, args.konvertrek_key, batch)
                matched = sum(1 for r in results if r["result"]["status"] == "matched")
                print(f"  Sent batch of {len(batch)}: {matched} matched")
                total_sent += len(batch)
                time.sleep(0.5)  # be gentle
            else:
                print(f"  [dry-run] would send {len(batch)} events")
            batch = []

        print(f"  Page {page}: {len(docs)} docs, {total_fetched} total fetched, {total_matched} invoices")

        if not data.get("next"):
            break
        page += 1

    # Send remaining
    if batch and not args.dry_run:
        results = send_batch(kr_client, args.konvertrek_key, batch)
        total_sent += len(batch)

    print(f"\nDone. Fetched={total_fetched}, invoices={total_matched}, sent={total_sent}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with --dry-run first**

```bash
venv\Scripts\python scripts/paperless_bulk_import.py \
  --paperless-url http://<paperless-host>:8000 \
  --paperless-token <TOKEN> \
  --konvertrek-url http://127.0.0.1:8080 \
  --konvertrek-key <KEY> \
  --dry-run
```

Expected output: lists pages with counts, no HTTP calls to konvertrek.

- [ ] **Step 3: Run for real**

Remove `--dry-run`. Monitor output — check for "not_matched" count. If too many not_matched, inspect the `doc_type` values returned and adjust `INVOICE_TYPES` set if Paperless uses different names.

- [ ] **Step 4: Commit**

```bash
git add scripts/paperless_bulk_import.py
git commit -m "feat: add Paperless bulk import script for existing documents"
```

---

## Self-Review

**Spec coverage checklist:**

| Requirement | Task |
|-------------|------|
| Local DB mirror of счет-фактур | Task 1, 3, 4 |
| Background incremental sync (APScheduler) | Task 5 |
| Initial sync via admin endpoint | Task 5 |
| Admin sync status endpoint | Task 5 |
| Documents перемещения fallback to 1C | Task 6 — `if normalized is None` |
| Backfill partner_name when resolved from 1C | Task 6 Step 4 |
| Full document report with all columns | Task 7, 10 |
| 1C mark timestamps in report | Task 7 (mark_reg/seal/ver subqueries) |
| Clickable Paperless link in report | Task 7 (`archive_download_url`), Task 10 (JS `<a href>`) |
| Paperless webhook (POST /api/webhooks/paperless) | Task 8 |
| API key auth for webhook | Task 8 |
| Paperless type filter: УПД/УКД pass, Доверенность skip | Task 8 `_is_invoice_type` |
| Date matching by day only (strip time) | Task 8 `find_matching_document` |
| Match by number + date + correspondent | Task 8 `find_matching_document` |
| Store both UNC path and HTTP download URL | Task 1 (`archive_storage_path` + `archive_download_url`), Task 8 |
| PATCH 1C kzvСсылкаНаКопию (UNC path) | Task 3 + Task 8 |
| Batch endpoint for existing Paperless docs | Task 8 `/paperless/batch` |
| Post-consume shell script | Task 9 |
| UI report page | Task 10 |
| Bulk import script for existing Paperless docs | Task 11 |
| disable_1c_timestamps flag | Already in config as `enable_1c_timestamps` — no change needed |

**Placeholder scan:** No TBD, TODO, or "implement later" — all steps contain actual code.

**Type consistency:** `OneCDocument` model fields match exactly what `_parse_invoice_row()` produces and what `_lookup_from_local_cache()` reads. `ReportDocumentRow` schema fields (`archive_download_url`, `archive_storage_path`) match what `list_report_documents()` puts in the dict. `PaperlessEvent` Pydantic model fields match what `process_paperless_event()` expects as kwargs. Task 11 script's `build_event()` produces the same shape as `PaperlessEvent`.

**Paperless type names** configured in the classifier must match `_INVOICE_TYPES = {"упд", "укд", "упд/укд"}` (case-insensitive). If actual type names differ — update the frozenset before deploying Task 8. Run Task 11 with `--dry-run` first to confirm match rates.
