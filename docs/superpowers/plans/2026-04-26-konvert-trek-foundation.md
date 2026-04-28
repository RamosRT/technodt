# Konvert-Trek MVP — Foundation & JSON API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation of Конверт-трек MVP — async FastAPI app with PostgreSQL persistence, OData 1С client, full set of `/api/*` JSON endpoints (envelopes, documents, seal, verify, dictionaries, admin reset), and a passing pytest suite. UI, printing, and production deployment are out of scope for this plan.

**Architecture:** 3-layer (`routers → services → models`). All I/O is async (SQLAlchemy 2.x async, httpx async, FastAPI async). OData client is the only external integration; failures are mapped to typed exceptions and rendered as `502 1c_unavailable` / `404 document_not_in_1c`. Tests use real Postgres (asyncpg) running locally; OData is mocked with `respx`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async + asyncpg, Alembic, pydantic-settings, httpx, pytest + pytest-asyncio + respx.

**Pre-flight (one-time, the engineer runs before Task 1):**
- `python --version` → must be 3.14.
- A local Postgres 16 instance reachable as `postgres://convert_track:convert_track@localhost:5432/convert_track` AND a separate `convert_track_test` database. If absent, run a docker container: `docker run -d --name pg-konvert -e POSTGRES_USER=convert_track -e POSTGRES_PASSWORD=convert_track -e POSTGRES_DB=convert_track -p 5432:5432 postgres:16` and then `docker exec pg-konvert psql -U convert_track -c "CREATE DATABASE convert_track_test;"`.
- `git status` clean except for the existing untracked `CLAUDE.md`, `project-overview.md`, `development.md`, `odata_metadata.xml`, `design/`, `docs/`, `.agents/`, `.claude/`, `.vscode/`, `skills-lock.json`. The first commit in this plan adds them.

**Source-of-truth references (do not duplicate, just consult):**
- Design spec: `docs/superpowers/specs/2026-04-26-konvert-trek-mvp-design.md`.
- Higher-level overview (Russian): `project-overview.md`.
- 1С EDMX schema (very large, do not load fully): `odata_metadata.xml`.

**Russian-language note:** error `detail` strings shown to UI are Russian; machine codes (`barcode_invalid` etc.) and identifiers stay English.

---

## File map (locked in before tasks)

```
pyproject.toml                          deps + tool config
.env.example                            sanitized template (real .env already exists, untracked)
alembic.ini
alembic/env.py
alembic/versions/0001_initial.py
app/__init__.py
app/config.py                           pydantic-settings Settings
app/db.py                               async engine + sessionmaker + get_session dep
app/main.py                             FastAPI app, lifespan, router wiring
app/auth.py                             operator cookie + admin token deps
app/exceptions.py                       AppError hierarchy + handler
app/models/__init__.py
app/models/base.py                      DeclarativeBase
app/models/branch.py
app/models/signer.py
app/models/envelope.py                  Envelope + EnvelopeStatus enum
app/models/envelope_document.py
app/models/audit_log.py
app/schemas/__init__.py
app/schemas/envelope.py
app/schemas/document.py
app/schemas/dictionary.py
app/schemas/verify.py
app/services/__init__.py
app/services/barcode.py                 doc_barcode_to_guid + envelope code generator
app/services/audit.py                   write_event helper
app/services/odata.py                   OneCClient (probe types, normalize, related lookup)
app/services/envelopes.py               create / get / add_doc / remove_doc / seal
app/services/verify.py                  start / scan / finish
app/services/dictionaries.py            branches + signers CRUD
app/routers/__init__.py
app/routers/api/__init__.py
app/routers/api/envelopes.py
app/routers/api/verify.py
app/routers/api/dictionaries.py
app/routers/api/admin.py
app/routers/api/health.py
tests/__init__.py
tests/conftest.py                       db engine, session, client, respx, fixtures
tests/fixtures/odata/peremeshchenie.json
tests/fixtures/odata/sf_upd.json
tests/fixtures/odata/sf_ukd.json
tests/fixtures/odata/realizatsiya.json
tests/fixtures/odata/not_found.json
tests/test_barcode.py
tests/test_audit.py
tests/test_odata.py
tests/test_envelopes_service.py
tests/test_verify_service.py
tests/test_api_envelopes.py
tests/test_api_verify.py
tests/test_api_dictionaries.py
tests/test_api_admin.py
tests/test_auth.py
```

---

## Task 1: Bootstrap project tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore` (already has the right entries; only verify and possibly add `alembic/versions/__pycache__`)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "convert-track"
version = "0.1.0"
description = "Конверт-трек: tracking accounting documents transferred between branches"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.118",
    "uvicorn[standard]>=0.34",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "httpx>=0.28",
    "jinja2>=3.1",
    "python-multipart>=0.0.20",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "respx>=0.22",
    "ruff>=0.8",
]

[build-system]
requires = ["setuptools>=70"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-x -q"

[tool.ruff]
line-length = 110
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [ ] **Step 2: Create `.env.example`**

```env
# Application
ENV=development
ADMIN_TOKEN=change-me-in-prod-please

# Database
DATABASE_URL=postgresql+asyncpg://convert_track:convert_track@localhost:5432/convert_track
DATABASE_URL_TEST=postgresql+asyncpg://convert_track:convert_track@localhost:5432/convert_track_test

# 1С OData
ODATA_BASE_URL=http://example.invalid/odata/standard.odata
ODATA_ADMIN_USER=odata.admin
ODATA_PASSWORD=replace-me
ODATA_TIMEOUT_SECONDS=60

# Envelope barcode
ENVELOPE_BC_PREFIX=
```

- [ ] **Step 3: Verify `.gitignore` already excludes `.env`, `__pycache__/`, `.pytest_cache/`, `venv/`** — it does. No change.

- [ ] **Step 4: Install in editable mode**

Run:
```bash
python -m venv venv
venv/Scripts/python -m pip install -U pip
venv/Scripts/python -m pip install -e ".[dev]"
```

Expected: install completes without errors, `venv/Scripts/pytest --version` prints a version.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example CLAUDE.md project-overview.md development.md odata_metadata.xml design/ docs/ .agents/ .claude/ .vscode/ skills-lock.json .gitignore
git commit -m "chore: bootstrap project tooling and bring design assets into git"
```

Note: `.env` is excluded by `.gitignore` and must NOT be added.

---

## Task 2: App skeleton — config, exceptions, healthcheck, main

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/exceptions.py`, `app/main.py`, `app/routers/__init__.py`, `app/routers/api/__init__.py`, `app/routers/api/health.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_health.py`

- [ ] **Step 1: Create `tests/test_health.py` (failing test)**

```python
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Create empty `tests/__init__.py` and `tests/conftest.py`**

`tests/__init__.py` is empty. `tests/conftest.py`:
```python
# Shared fixtures will be added in later tasks. Empty for now.
```

- [ ] **Step 3: Run the test, expect failure**

Run: `venv/Scripts/python -m pytest tests/test_health.py -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 4: Create `app/__init__.py` (empty), `app/config.py`**

`app/config.py`:
```python
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["development", "test", "production"] = "development"
    admin_token: str = Field(min_length=8)

    database_url: str
    database_url_test: str | None = None

    odata_base_url: str
    odata_admin_user: str
    odata_password: str
    odata_timeout_seconds: int = 60

    envelope_bc_prefix: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Create `app/exceptions.py`**

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base for domain errors mapped to JSON {detail, code}."""
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, detail: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class BarcodeError(AppError):
    status_code = 400
    code = "barcode_invalid"


class DocumentNotInOneC(AppError):
    status_code = 404
    code = "document_not_in_1c"


class OneCUnavailable(AppError):
    status_code = 502
    code = "1c_unavailable"


class EnvelopeNotFound(AppError):
    status_code = 404
    code = "envelope_not_found"


class EnvelopeNotDraft(AppError):
    status_code = 409
    code = "envelope_not_draft"


class DocumentAlreadyInEnvelope(AppError):
    status_code = 409
    code = "document_already_in_envelope"


class VerificationUnscanned(AppError):
    status_code = 409
    code = "verification_unscanned"


class InvalidSealPayload(AppError):
    status_code = 400
    code = "invalid_seal_payload"


class AdminTokenInvalid(AppError):
    status_code = 401
    code = "admin_token_invalid"


class OperatorRequired(AppError):
    status_code = 401
    code = "operator_required"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})
```

- [ ] **Step 6: Create `app/routers/__init__.py` (empty), `app/routers/api/__init__.py` (empty), `app/routers/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Create `app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.exceptions import AppError, app_error_handler
from app.routers.api import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # OData client and other long-lived resources will be wired in later tasks.
    yield


app = FastAPI(title="Конверт-трек", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health.router)
```

- [ ] **Step 8: Run the test, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_health.py -x`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/ tests/
git commit -m "feat: minimal FastAPI app with config, exceptions, healthcheck"
```

---

## Task 3: Async DB session

**Files:**
- Create: `app/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test `tests/test_db.py`**

```python
import pytest
from sqlalchemy import text

from app.db import get_engine, get_session_factory


@pytest.mark.asyncio
async def test_can_open_session_and_select_one(monkeypatch):
    # Use the test DB URL.
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "database_url", s.database_url_test or s.database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_db.py -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Implement `app/db.py`**

```python
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_db.py -x`
Expected: PASS (requires the `convert_track_test` database to exist — see Pre-flight).

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: async SQLAlchemy engine and session factory"
```

---

## Task 4: SQLAlchemy models

**Files:**
- Create: `app/models/__init__.py`, `app/models/base.py`, `app/models/branch.py`, `app/models/signer.py`, `app/models/envelope.py`, `app/models/envelope_document.py`, `app/models/audit_log.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test `tests/test_models.py`**

```python
def test_all_models_registered():
    from app.models import Base, Branch, Signer, Envelope, EnvelopeStatus, EnvelopeDocument, AuditLog
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"branches", "signers", "envelopes", "envelope_documents", "audit_log"}
    # enum
    assert {s.value for s in EnvelopeStatus} == {"draft", "sealed", "verified", "verified_with_discrepancy"}
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_models.py -x`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/models/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Implement `app/models/branch.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Implement `app/models/signer.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Signer(Base):
    __tablename__ = "signers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Implement `app/models/envelope.py`**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class EnvelopeStatus(enum.Enum):
    draft = "draft"
    sealed = "sealed"
    verified = "verified"
    verified_with_discrepancy = "verified_with_discrepancy"


class Envelope(Base):
    __tablename__ = "envelopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    barcode: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    status: Mapped[EnvelopeStatus] = mapped_column(
        Enum(EnvelopeStatus, name="envelope_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=EnvelopeStatus.draft,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(200))
    origin_branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    destination_branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    signer_sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signers.id"))
    signer_receiver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signers.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["EnvelopeDocument"]] = relationship(
        back_populates="envelope", cascade="all, delete-orphan", lazy="selectin"
    )
```

- [ ] **Step 7: Implement `app/models/envelope_document.py`**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class EnvelopeDocument(Base):
    __tablename__ = "envelope_documents"
    __table_args__ = (UniqueConstraint("envelope_id", "doc_guid", name="uq_envelope_doc_guid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("envelopes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    doc_barcode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    doc_entity: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    related_realization_number: Mapped[str | None] = mapped_column(String(50))
    related_realization_date: Mapped[date | None] = mapped_column(Date)
    raw_1c_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scanned_at_verification: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    envelope: Mapped["Envelope"] = relationship(back_populates="documents")
```

- [ ] **Step 8: Implement `app/models/audit_log.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    envelope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("envelopes.id", ondelete="SET NULL"), index=True
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="system")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
```

- [ ] **Step 9: Implement `app/models/__init__.py`**

```python
from .base import Base
from .branch import Branch
from .signer import Signer
from .envelope import Envelope, EnvelopeStatus
from .envelope_document import EnvelopeDocument
from .audit_log import AuditLog

__all__ = ["Base", "Branch", "Signer", "Envelope", "EnvelopeStatus", "EnvelopeDocument", "AuditLog"]
```

- [ ] **Step 10: Run test, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_models.py -x`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add app/models/ tests/test_models.py
git commit -m "feat: SQLAlchemy models for branches, signers, envelopes, documents, audit"
```

---

## Task 5: Alembic init and initial migration

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial.py`

- [ ] **Step 1: Create `alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@host/dbname  ; overridden in env.py

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `alembic/script.py.mako`**

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Create `alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Create `alembic/versions/__init__.py` (empty file) and `alembic/versions/0001_initial.py`**

```python
"""initial

Revision ID: 0001
Revises:
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "signers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    envelope_status = postgresql.ENUM(
        "draft", "sealed", "verified", "verified_with_discrepancy",
        name="envelope_status",
    )
    envelope_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "envelopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("barcode", sa.String(40), nullable=False, unique=True),
        sa.Column("status", envelope_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sealed_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("verified_by", sa.String(200)),
        sa.Column("origin_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("destination_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("signer_sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signers.id")),
        sa.Column("signer_receiver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signers.id")),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_envelopes_barcode", "envelopes", ["barcode"], unique=True)
    op.create_table(
        "envelope_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("envelopes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_barcode", sa.String(64), nullable=False),
        sa.Column("doc_guid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_entity", sa.String(100), nullable=False),
        sa.Column("doc_kind", sa.String(50), nullable=False),
        sa.Column("doc_number", sa.String(50), nullable=False),
        sa.Column("doc_date", sa.Date, nullable=False),
        sa.Column("related_realization_number", sa.String(50)),
        sa.Column("related_realization_date", sa.Date),
        sa.Column("raw_1c_payload", postgresql.JSONB, nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("scanned_at_verification", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("envelope_id", "doc_guid", name="uq_envelope_doc_guid"),
    )
    op.create_index("ix_envelope_documents_envelope_id", "envelope_documents", ["envelope_id"])
    op.create_index("ix_envelope_documents_doc_barcode", "envelope_documents", ["doc_barcode"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("envelopes.id", ondelete="SET NULL")),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("actor", sa.String(200), nullable=False, server_default="system"),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_envelope_id", "audit_log", ["envelope_id"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("envelope_documents")
    op.drop_table("envelopes")
    op.drop_table("signers")
    op.drop_table("branches")
    op.execute("DROP TYPE envelope_status")
```

- [ ] **Step 5: Apply against the dev DB**

Run:
```bash
venv/Scripts/python -m alembic upgrade head
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial`. Then `psql` (or any client) shows tables `branches, signers, envelopes, envelope_documents, audit_log`.

- [ ] **Step 6: Apply against the test DB**

Run:
```bash
DATABASE_URL=postgresql+asyncpg://convert_track:convert_track@localhost:5432/convert_track_test venv/Scripts/python -m alembic upgrade head
```
On Windows bash, use `DATABASE_URL=...` inline (Git Bash supports it). Expected: same upgrade message; tables in `convert_track_test`.

- [ ] **Step 7: Commit**

```bash
git add alembic.ini alembic/
git commit -m "feat: alembic initial migration creates all tables"
```

---

## Task 6: Test infrastructure (conftest with DB session, FastAPI client, respx)

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Replace `tests/conftest.py` with full fixtures**

```python
import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_engine, get_session, get_session_factory
from app.main import app
from app.models import Base


def _test_db_url() -> str:
    s = get_settings()
    return s.database_url_test or s.database_url


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(_test_db_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def truncate_tables(test_engine):
    """Wipe all data between tests; schema stays."""
    async with test_engine.begin() as conn:
        for tbl in ("audit_log", "envelope_documents", "envelopes", "signers", "branches"):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:
    """ASGI client wired so app uses the test DB via dependency override."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(monkeypatch):
    token = "test-admin-token-12345"
    monkeypatch.setenv("ADMIN_TOKEN", token)
    get_settings.cache_clear()
    return token
```

- [ ] **Step 2: Re-run the existing health test to make sure conftest changes did not break anything**

Run: `venv/Scripts/python -m pytest tests/test_health.py -x`
Expected: PASS.

- [ ] **Step 3: Run the full suite**

Run: `venv/Scripts/python -m pytest -x`
Expected: PASS (test_health, test_db, test_models). The autouse `truncate_tables` will hit the test DB.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: shared conftest with test engine, session, ASGI client"
```

---

## Task 7: Barcode service — doc_barcode_to_guid

**Files:**
- Create: `app/services/__init__.py` (empty)
- Create: `app/services/barcode.py`
- Create: `tests/test_barcode.py`

- [ ] **Step 1: Write failing tests `tests/test_barcode.py`**

```python
import uuid
import pytest

from app.exceptions import BarcodeError
from app.services.barcode import doc_barcode_to_guid


def test_doc_barcode_to_guid_known_value():
    # Sanity-check round trip: take a UUID, encode as int, treat as decimal barcode.
    g = uuid.UUID("12345678-1234-5678-1234-567812345678")
    n = int.from_bytes(g.bytes, "big")
    assert doc_barcode_to_guid(str(n)) == g


def test_doc_barcode_to_guid_zero():
    assert doc_barcode_to_guid("0") == uuid.UUID(int=0)


def test_doc_barcode_to_guid_max_128_bit():
    n = (1 << 128) - 1
    assert doc_barcode_to_guid(str(n)).int == n


def test_doc_barcode_to_guid_too_large_raises():
    n = 1 << 128  # 129 bits
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid(str(n))


def test_doc_barcode_to_guid_non_digit_raises():
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid("12abc")


def test_doc_barcode_to_guid_empty_raises():
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid("")
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_barcode.py -x`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/services/barcode.py` (partial — only `doc_barcode_to_guid` for now)**

```python
import uuid

from app.exceptions import BarcodeError


def doc_barcode_to_guid(barcode: str) -> uuid.UUID:
    if not barcode or not barcode.isdigit():
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    n = int(barcode)
    if n.bit_length() > 128:
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    return uuid.UUID(bytes=n.to_bytes(16, "big"))
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_barcode.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/__init__.py app/services/barcode.py tests/test_barcode.py
git commit -m "feat: barcode_to_guid conversion with validation"
```

---

## Task 8: Barcode service — envelope code generator

**Files:**
- Modify: `app/services/barcode.py`
- Modify: `tests/test_barcode.py`

- [ ] **Step 1: Add failing tests for the generator**

Append to `tests/test_barcode.py`:
```python
import re
from app.services.barcode import generate_envelope_codes


def test_generate_envelope_codes_format():
    number, barcode = generate_envelope_codes()
    assert re.fullmatch(r"ТА-\d{16}", number)
    assert re.fullmatch(r"\d{16}", barcode)
    # number is just the prefix + barcode
    assert number == f"ТА-{barcode}"


def test_generate_envelope_codes_with_prefix(monkeypatch):
    from app import config
    monkeypatch.setenv("ENVELOPE_BC_PREFIX", "99")
    config.get_settings.cache_clear()
    number, barcode = generate_envelope_codes()
    assert barcode.startswith("99")
    assert len(barcode) == 16


def test_generate_envelope_codes_uniqueness_across_many_calls():
    seen = set()
    for _ in range(1000):
        _, bc = generate_envelope_codes()
        assert bc not in seen
        seen.add(bc)
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_barcode.py -x`
Expected: FAIL — `ImportError: cannot import name 'generate_envelope_codes'`.

- [ ] **Step 3: Add the generator to `app/services/barcode.py`**

Append:
```python
import secrets

from app.config import get_settings


def generate_envelope_codes() -> tuple[str, str]:
    """Returns (number, barcode). number = 'ТА-' + barcode. barcode is 16 digits."""
    prefix = get_settings().envelope_bc_prefix
    digits_needed = 16 - len(prefix)
    if digits_needed <= 0:
        raise ValueError("ENVELOPE_BC_PREFIX must be shorter than 16 chars")
    tail = "".join(secrets.choice("0123456789") for _ in range(digits_needed))
    barcode = prefix + tail
    return f"ТА-{barcode}", barcode
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_barcode.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/barcode.py tests/test_barcode.py
git commit -m "feat: cryptographically random 16-digit envelope number and barcode"
```

---

## Task 9: Audit service — write_event

**Files:**
- Create: `app/services/audit.py`
- Create: `tests/test_audit.py`

- [ ] **Step 1: Write failing test `tests/test_audit.py`**

```python
import uuid

import pytest
from sqlalchemy import select

from app.models import AuditLog
from app.services.audit import write_event


@pytest.mark.asyncio
async def test_write_event_persists_row(db_session):
    env_id = uuid.uuid4()
    await write_event(db_session, envelope_id=env_id, event="create", actor="ramos", payload={"x": 1})
    await db_session.commit()
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event == "create"
    assert rows[0].actor == "ramos"
    assert rows[0].envelope_id == env_id
    assert rows[0].payload == {"x": 1}


@pytest.mark.asyncio
async def test_write_event_default_actor_and_payload(db_session):
    await write_event(db_session, envelope_id=None, event="dictionary_change")
    await db_session.commit()
    row = (await db_session.execute(select(AuditLog))).scalar_one()
    assert row.actor == "system"
    assert row.payload == {}
    assert row.envelope_id is None
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_audit.py -x`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `app/services/audit.py`**

```python
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def write_event(
    session: AsyncSession,
    *,
    envelope_id: uuid.UUID | None,
    event: str,
    actor: str = "system",
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(envelope_id=envelope_id, event=event, actor=actor, payload=payload or {})
    session.add(row)
    await session.flush()
    return row
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_audit.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/audit.py tests/test_audit.py
git commit -m "feat: audit log write_event helper"
```

---

## Task 10: Auth — operator cookie + admin token deps

**Files:**
- Create: `app/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests `tests/test_auth.py`**

```python
import pytest
from fastapi import APIRouter

from app.auth import require_admin, require_operator
from app.main import app


@pytest.fixture(autouse=True)
def _add_probe_routes():
    router = APIRouter()

    @router.get("/_probe/operator")
    async def probe_operator(name: str = require_operator()):  # noqa: B008
        return {"operator": name}

    @router.get("/_probe/admin")
    async def probe_admin(_=require_admin()):  # noqa: B008
        return {"ok": True}

    app.include_router(router)
    yield
    app.routes[:] = [r for r in app.routes if not getattr(r, "path", "").startswith("/_probe")]


@pytest.mark.asyncio
async def test_operator_required_returns_401_without_cookie(client):
    r = await client.get("/_probe/operator")
    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_operator_required_returns_name_with_cookie(client):
    client.cookies.set("operator_name", "Иван")
    r = await client.get("/_probe/operator")
    assert r.status_code == 200
    assert r.json() == {"operator": "Иван"}


@pytest.mark.asyncio
async def test_admin_required_returns_401_without_header(client, admin_token):
    r = await client.get("/_probe/admin")
    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_required_passes_with_correct_header(client, admin_token):
    r = await client.get("/_probe/admin", headers={"X-Admin-Token": admin_token})
    assert r.status_code == 200
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_auth.py -x`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `app/auth.py`**

```python
from fastapi import Cookie, Header

from app.config import get_settings
from app.exceptions import AdminTokenInvalid, OperatorRequired


def require_operator():
    async def dep(operator_name: str | None = Cookie(default=None)) -> str:
        if not operator_name:
            raise OperatorRequired("Введите имя оператора")
        return operator_name

    from fastapi import Depends
    return Depends(dep)


def require_admin():
    async def dep(x_admin_token: str | None = Header(default=None)) -> None:
        expected = get_settings().admin_token
        if not x_admin_token or x_admin_token != expected:
            raise AdminTokenInvalid("Неверный токен администратора")

    from fastapi import Depends
    return Depends(dep)
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_auth.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/auth.py tests/test_auth.py
git commit -m "feat: operator cookie + admin token FastAPI dependencies"
```

---

## Task 11: OData client — fixtures and skeleton

**Files:**
- Create: `tests/fixtures/odata/peremeshchenie.json`, `sf_upd.json`, `sf_ukd.json`, `realizatsiya.json`
- Create: `app/services/odata.py`
- Create: `tests/test_odata.py`

The fixtures are synthetic but follow the EDMX shape. Real fixtures will replace them when the user tunnels to 1С.

- [ ] **Step 1: Create fixtures**

`tests/fixtures/odata/peremeshchenie.json`:
```json
{
  "Ref_Key": "11111111-1111-1111-1111-111111111111",
  "Number": "ПЕР-000123",
  "Date": "2026-04-20T00:00:00",
  "Posted": true
}
```

`tests/fixtures/odata/sf_upd.json`:
```json
{
  "Ref_Key": "22222222-2222-2222-2222-222222222222",
  "Number": "СФВ-000456",
  "Date": "2026-04-21T00:00:00",
  "Корректировочный": false,
  "ДокументОснование_Key": "33333333-3333-3333-3333-333333333333",
  "ДокументОснование_Type": "StandardODATA.Document_РеализацияТоваровУслуг"
}
```

`tests/fixtures/odata/sf_ukd.json`:
```json
{
  "Ref_Key": "44444444-4444-4444-4444-444444444444",
  "Number": "СФВ-000789",
  "Date": "2026-04-22T00:00:00",
  "Корректировочный": true,
  "ДокументОснование_Key": "33333333-3333-3333-3333-333333333333",
  "ДокументОснование_Type": "StandardODATA.Document_РеализацияТоваровУслуг"
}
```

`tests/fixtures/odata/realizatsiya.json`:
```json
{
  "Ref_Key": "33333333-3333-3333-3333-333333333333",
  "Number": "РЕА-000999",
  "Date": "2026-04-19T00:00:00"
}
```

- [ ] **Step 2: Write failing test `tests/test_odata.py`** (skeleton only — type probe + auth)

```python
import json
import uuid
from pathlib import Path

import httpx
import pytest
import respx

from app.exceptions import DocumentNotInOneC, OneCUnavailable
from app.services.odata import KNOWN_DOC_TYPES, OneCClient, SELECT_FIELDS

FIXTURES = Path(__file__).parent / "fixtures" / "odata"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def base_url():
    return "http://1c.example/odata/standard.odata"


@pytest.fixture
def client(base_url):
    return OneCClient(base_url=base_url, user="u", password="p", timeout=5)


@pytest.mark.asyncio
async def test_known_doc_types_are_two():
    assert KNOWN_DOC_TYPES == ("Document_ПеремещениеТоваров", "Document_СчетФактураВыданный")
    assert "Document_ПеремещениеТоваров" in SELECT_FIELDS


@pytest.mark.asyncio
async def test_fetch_document_returns_peremeshchenie_on_first_try(client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(200, json=_load("peremeshchenie.json"))
        entity, payload = await client.fetch_document(guid)
    assert entity == "Document_ПеремещениеТоваров"
    assert payload["Number"] == "ПЕР-000123"


@pytest.mark.asyncio
async def test_fetch_document_falls_through_to_second_type(client, base_url):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        entity, payload = await client.fetch_document(guid)
    assert entity == "Document_СчетФактураВыданный"


@pytest.mark.asyncio
async def test_fetch_document_all_404_raises_not_found(client, base_url):
    guid = uuid.UUID("99999999-9999-9999-9999-999999999999")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(404)
        with pytest.raises(DocumentNotInOneC):
            await client.fetch_document(guid)


@pytest.mark.asyncio
async def test_fetch_document_401_raises_unavailable(client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(401)
        with pytest.raises(OneCUnavailable):
            await client.fetch_document(guid)


@pytest.mark.asyncio
async def test_fetch_document_network_error_raises_unavailable(client, base_url):
    guid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").mock(side_effect=httpx.ConnectError("boom"))
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(OneCUnavailable):
            await client.fetch_document(guid)
```

- [ ] **Step 3: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_odata.py -x`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `app/services/odata.py` (skeleton)**

```python
import logging
import uuid
from typing import Any

import httpx

from app.exceptions import DocumentNotInOneC, OneCUnavailable

log = logging.getLogger(__name__)

SELECT_FIELDS: dict[str, tuple[str, ...]] = {
    "Document_ПеремещениеТоваров": ("Number", "Date"),
    "Document_СчетФактураВыданный": (
        "Number",
        "Date",
        "Корректировочный",
        "ДокументОснование",
        "ДокументОснование_Key",
        "ДокументОснование_Type",
    ),
}

KNOWN_DOC_TYPES: tuple[str, ...] = (
    "Document_ПеремещениеТоваров",
    "Document_СчетФактураВыданный",
)


class OneCClient:
    def __init__(self, *, base_url: str, user: str, password: str, timeout: int = 60):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(user, password),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_document(self, guid: uuid.UUID) -> tuple[str, dict[str, Any]]:
        last_exc: Exception | None = None
        for entity in KNOWN_DOC_TYPES:
            try:
                resp = await self._get_entity(entity, guid)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
                last_exc = e
                continue
            if resp.status_code == 200:
                return entity, resp.json()
            if resp.status_code == 401:
                raise OneCUnavailable("Не удалось авторизоваться в 1С")
            if resp.status_code == 404:
                continue
            raise OneCUnavailable(f"1С вернула неожиданный статус {resp.status_code}")
        if last_exc is not None:
            raise OneCUnavailable("1С недоступна") from last_exc
        raise DocumentNotInOneC("Документ не найден в 1С")

    async def _get_entity(self, entity: str, guid: uuid.UUID) -> httpx.Response:
        fields = ",".join(SELECT_FIELDS[entity])
        url = f"/{entity}(guid'{guid}')"
        return await self._client.get(url, params={"$format": "json", "$select": fields})
```

- [ ] **Step 5: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_odata.py -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/odata.py tests/test_odata.py tests/fixtures/
git commit -m "feat: OData client with sequential type probing"
```

---

## Task 12: OData client — payload normalization (doc_kind, related realization)

**Files:**
- Modify: `app/services/odata.py`
- Modify: `tests/test_odata.py`

- [ ] **Step 1: Add failing tests for `normalize` and the `lookup_document_with_related` orchestrator**

Append to `tests/test_odata.py`:
```python
from datetime import date as _date

from app.services.odata import normalize_document


def test_normalize_peremeshchenie():
    payload = _load("peremeshchenie.json")
    n = normalize_document("Document_ПеремещениеТоваров", payload)
    assert n.doc_kind == "Перемещение товаров"
    assert n.doc_number == "ПЕР-000123"
    assert n.doc_date == _date(2026, 4, 20)
    assert n.related_realization_ref is None


def test_normalize_upd_with_related():
    payload = _load("sf_upd.json")
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.doc_kind == "УПД"
    assert n.doc_number == "СФВ-000456"
    assert n.related_realization_ref is not None
    assert str(n.related_realization_ref.guid) == "33333333-3333-3333-3333-333333333333"
    assert n.related_realization_ref.entity == "Document_РеализацияТоваровУслуг"


def test_normalize_ukd():
    payload = _load("sf_ukd.json")
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.doc_kind == "УКД"


def test_normalize_sf_without_related_returns_none():
    payload = {"Number": "X", "Date": "2026-04-22T00:00:00", "Корректировочный": False}
    n = normalize_document("Document_СчетФактураВыданный", payload)
    assert n.related_realization_ref is None


@pytest.mark.asyncio
async def test_lookup_with_related_fills_related_fields(client, base_url):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        mock.get(
            "/Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')"
        ).respond(200, json=_load("realizatsiya.json"))
        result = await client.lookup_document_with_related(guid)
    assert result.doc_kind == "УПД"
    assert result.related_realization_number == "РЕА-000999"
    assert result.related_realization_date == _date(2026, 4, 19)


@pytest.mark.asyncio
async def test_lookup_with_related_swallows_realization_error(client, base_url, caplog):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    with respx.mock(base_url=base_url) as mock:
        mock.get(f"/Document_ПеремещениеТоваров(guid'{guid}')").respond(404)
        mock.get(f"/Document_СчетФактураВыданный(guid'{guid}')").respond(200, json=_load("sf_upd.json"))
        mock.get(
            "/Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')"
        ).mock(side_effect=httpx.ConnectError("boom"))
        result = await client.lookup_document_with_related(guid)
    assert result.related_realization_number is None
    assert result.related_realization_date is None
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_odata.py -x`
Expected: FAIL — `normalize_document` / `lookup_document_with_related` missing.

- [ ] **Step 3: Extend `app/services/odata.py`**

Append:
```python
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class RelatedRef:
    guid: uuid.UUID
    entity: str  # short entity name without "StandardODATA." prefix


@dataclass
class NormalizedDocument:
    entity: str
    doc_kind: str
    doc_number: str
    doc_date: date
    related_realization_ref: RelatedRef | None
    raw_payload: dict[str, Any]
    related_realization_number: str | None = None
    related_realization_date: date | None = None


def _parse_odata_date(s: str | None) -> date:
    if not s:
        raise ValueError("missing Date")
    # 1С returns ISO 8601 like "2026-04-20T00:00:00"; strip time.
    return datetime.fromisoformat(s).date()


def _extract_related_ref(payload: dict[str, Any]) -> RelatedRef | None:
    raw_type = payload.get("ДокументОснование_Type")
    raw_key = payload.get("ДокументОснование_Key")
    if not raw_type or not raw_key:
        return None
    # Strip "StandardODATA." prefix if present.
    short = raw_type.split(".", 1)[-1]
    if not short.startswith("Document_") or "Реализация" not in short:
        return None
    try:
        guid = uuid.UUID(str(raw_key))
    except (ValueError, AttributeError):
        return None
    return RelatedRef(guid=guid, entity=short)


def normalize_document(entity: str, payload: dict[str, Any]) -> NormalizedDocument:
    if entity == "Document_ПеремещениеТоваров":
        kind = "Перемещение товаров"
        related = None
    elif entity == "Document_СчетФактураВыданный":
        kind = "УКД" if payload.get("Корректировочный") else "УПД"
        related = _extract_related_ref(payload)
    else:
        raise ValueError(f"unknown entity {entity}")
    return NormalizedDocument(
        entity=entity,
        doc_kind=kind,
        doc_number=str(payload.get("Number", "")),
        doc_date=_parse_odata_date(payload.get("Date")),
        related_realization_ref=related,
        raw_payload=payload,
    )
```

Then add `lookup_document_with_related` method to `OneCClient`:
```python
    async def lookup_document_with_related(self, guid: uuid.UUID) -> NormalizedDocument:
        entity, payload = await self.fetch_document(guid)
        normalized = normalize_document(entity, payload)
        if normalized.related_realization_ref is not None:
            ref = normalized.related_realization_ref
            try:
                resp = await self._get_realization(ref.entity, ref.guid)
                if resp.status_code == 200:
                    rp = resp.json()
                    normalized.related_realization_number = str(rp.get("Number", ""))
                    normalized.related_realization_date = _parse_odata_date(rp.get("Date"))
                else:
                    log.warning("realization lookup %s returned %s", ref.guid, resp.status_code)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as e:
                log.warning("realization lookup %s failed: %s", ref.guid, e)
        return normalized

    async def _get_realization(self, entity: str, guid: uuid.UUID) -> httpx.Response:
        url = f"/{entity}(guid'{guid}')"
        return await self._client.get(url, params={"$format": "json", "$select": "Number,Date"})
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_odata.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/odata.py tests/test_odata.py
git commit -m "feat: OData payload normalization and related realization lookup"
```

---

## Task 13: OneC client lifespan wiring

**Files:**
- Modify: `app/main.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update `app/main.py` to construct/close `OneCClient` in lifespan**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.exceptions import AppError, app_error_handler
from app.routers.api import health
from app.services.odata import OneCClient


def get_one_c_client() -> OneCClient:
    """Dependency override target. Real client lives on app.state."""
    raise RuntimeError("OneCClient not initialized — lifespan did not run")


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
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(title="Конверт-трек", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health.router)
```

- [ ] **Step 2: Update `tests/conftest.py` `client` fixture to override `get_one_c_client` with a stub**

Replace the `client` fixture:
```python
@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_session():
        async with factory() as s:
            yield s

    from app.main import get_one_c_client
    from app.services.odata import OneCClient
    stub = OneCClient(base_url="http://1c.example/odata/standard.odata", user="u", password="p", timeout=5)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_one_c_client] = lambda: stub

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await stub.aclose()
```

- [ ] **Step 3: Run the suite**

Run: `venv/Scripts/python -m pytest -x`
Expected: PASS (no behavior changed yet for routes; lifespan just wires the client).

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/conftest.py
git commit -m "feat: lifespan-managed shared OneCClient with dependency override"
```

---

## Task 14: Schemas — pydantic DTOs

**Files:**
- Create: `app/schemas/__init__.py` (empty), `app/schemas/envelope.py`, `app/schemas/document.py`, `app/schemas/dictionary.py`, `app/schemas/verify.py`

- [ ] **Step 1: Create `app/schemas/document.py`**

```python
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_barcode: str
    doc_guid: uuid.UUID
    doc_entity: str
    doc_kind: str
    doc_number: str
    doc_date: date
    related_realization_number: str | None = None
    related_realization_date: date | None = None
    added_at: datetime
    scanned_at_verification: datetime | None = None


class DocumentAddRequest(BaseModel):
    barcode: str
```

- [ ] **Step 2: Create `app/schemas/envelope.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import EnvelopeStatus
from app.schemas.document import DocumentOut


class EnvelopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    barcode: str
    status: EnvelopeStatus
    created_at: datetime
    sealed_at: datetime | None = None
    verified_at: datetime | None = None
    created_by: str
    verified_by: str | None = None
    origin_branch_id: uuid.UUID | None = None
    destination_branch_id: uuid.UUID | None = None
    signer_sender_id: uuid.UUID | None = None
    signer_receiver_id: uuid.UUID | None = None
    notes: str | None = None
    documents: list[DocumentOut] = []


class SealRequest(BaseModel):
    signer_sender_id: uuid.UUID
    signer_receiver_id: uuid.UUID
    origin_branch_id: uuid.UUID
    destination_branch_id: uuid.UUID
    notes: str | None = None
```

- [ ] **Step 3: Create `app/schemas/dictionary.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, Field


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BranchPatch(BaseModel):
    is_active: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)


class SignerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last_name: str
    first_name: str
    is_active: bool


class SignerCreate(BaseModel):
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)


class SignerPatch(BaseModel):
    is_active: bool | None = None
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
```

- [ ] **Step 4: Create `app/schemas/verify.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class VerifyScanRequest(BaseModel):
    barcode: str


class VerifyScanResponse(BaseModel):
    matched: bool
    doc_id: uuid.UUID | None = None
    scanned_at: datetime | None = None
    reason: str | None = None  # "not_in_envelope" when matched=False


class VerifyFinishRequest(BaseModel):
    force: bool = False


class VerifyFinishResponse(BaseModel):
    status: str  # "verified" | "verified_with_discrepancy"
    missing_docs: list[uuid.UUID] = []
```

- [ ] **Step 5: Empty `app/schemas/__init__.py`**

Just create the file with no content (a comment is fine).

- [ ] **Step 6: Quick smoke**

Run: `venv/Scripts/python -c "from app.schemas.envelope import EnvelopeOut, SealRequest; from app.schemas.dictionary import BranchOut, BranchCreate; from app.schemas.verify import VerifyScanResponse; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/
git commit -m "feat: pydantic DTOs for envelopes, documents, dictionaries, verify"
```

---

## Task 15: Envelope service — create

**Files:**
- Create: `app/services/envelopes.py`
- Create: `tests/test_envelopes_service.py`

- [ ] **Step 1: Failing test `tests/test_envelopes_service.py`**

```python
import pytest
from sqlalchemy import select

from app.models import AuditLog, Envelope, EnvelopeStatus
from app.services import envelopes as svc


@pytest.mark.asyncio
async def test_create_envelope_returns_draft_with_codes(db_session):
    env = await svc.create_envelope(db_session, operator="Иван")
    await db_session.commit()
    assert env.status == EnvelopeStatus.draft
    assert env.created_by == "Иван"
    assert env.number.startswith("ТА-")
    assert env.barcode and env.barcode.isdigit()
    assert env.number == f"ТА-{env.barcode}"

    saved = (await db_session.execute(select(Envelope))).scalar_one()
    assert saved.id == env.id

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(audits) == 1
    assert audits[0].event == "create"
    assert audits[0].actor == "Иван"
    assert audits[0].envelope_id == env.id
```

- [ ] **Step 2: Run, expect fail**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement create in `app/services/envelopes.py`**

```python
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Envelope, EnvelopeStatus
from app.services.audit import write_event
from app.services.barcode import generate_envelope_codes


MAX_CODE_RETRIES = 5


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
    raise RuntimeError(f"could not generate unique envelope codes after {MAX_CODE_RETRIES} retries") from last_exc
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py tests/test_envelopes_service.py
git commit -m "feat: create_envelope service with retry on barcode collision"
```

---

## Task 16: Envelope service — get_by_id, get_by_barcode

**Files:**
- Modify: `app/services/envelopes.py`
- Modify: `tests/test_envelopes_service.py`

- [ ] **Step 1: Failing tests**

Append to `tests/test_envelopes_service.py`:
```python
from app.exceptions import EnvelopeNotFound


@pytest.mark.asyncio
async def test_get_by_id_returns_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    fetched = await svc.get_by_id(db_session, env.id)
    assert fetched.id == env.id


@pytest.mark.asyncio
async def test_get_by_id_not_found_raises(db_session):
    import uuid as _u
    with pytest.raises(EnvelopeNotFound):
        await svc.get_by_id(db_session, _u.uuid4())


@pytest.mark.asyncio
async def test_get_by_barcode_returns_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    fetched = await svc.get_by_barcode(db_session, env.barcode)
    assert fetched.id == env.id


@pytest.mark.asyncio
async def test_get_by_barcode_not_found_raises(db_session):
    with pytest.raises(EnvelopeNotFound):
        await svc.get_by_barcode(db_session, "0000000000000000")
```

- [ ] **Step 2: Run, expect fail**

Expected: FAIL — `get_by_id`/`get_by_barcode` missing.

- [ ] **Step 3: Implement getters in `app/services/envelopes.py`**

Append:
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.exceptions import EnvelopeNotFound


async def get_by_id(session: AsyncSession, envelope_id: uuid.UUID) -> Envelope:
    stmt = select(Envelope).where(Envelope.id == envelope_id).options(selectinload(Envelope.documents))
    env = (await session.execute(stmt)).scalar_one_or_none()
    if env is None:
        raise EnvelopeNotFound(f"Конверт {envelope_id} не найден")
    return env


async def get_by_barcode(session: AsyncSession, barcode: str) -> Envelope:
    stmt = select(Envelope).where(Envelope.barcode == barcode).options(selectinload(Envelope.documents))
    env = (await session.execute(stmt)).scalar_one_or_none()
    if env is None:
        raise EnvelopeNotFound(f"Конверт со ШК {barcode} не найден")
    return env
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py tests/test_envelopes_service.py
git commit -m "feat: get_by_id and get_by_barcode envelope lookups"
```

---

## Task 17: Envelope service — add_document

**Files:**
- Modify: `app/services/envelopes.py`
- Modify: `tests/test_envelopes_service.py`

- [ ] **Step 1: Failing tests**

Append to `tests/test_envelopes_service.py`:
```python
import uuid
from datetime import date as _date
from unittest.mock import AsyncMock

from app.services.odata import NormalizedDocument


def _normalized_peremeshchenie() -> NormalizedDocument:
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-000123",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-000123", "Date": "2026-04-20T00:00:00"},
    )


@pytest.mark.asyncio
async def test_add_document_happy_path(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()

    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()

    barcode = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    doc = await svc.add_document(db_session, envelope=env, barcode=barcode,
                                  operator="A", one_c=one_c)
    await db_session.commit()
    assert doc.doc_kind == "Перемещение товаров"
    assert doc.doc_number == "ПЕР-000123"
    assert doc.doc_barcode == barcode
    assert doc.raw_1c_payload == {"Number": "ПЕР-000123", "Date": "2026-04-20T00:00:00"}


@pytest.mark.asyncio
async def test_add_document_rejects_when_envelope_sealed(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    await db_session.commit()
    one_c = AsyncMock()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.add_document(db_session, envelope=env, barcode="123", operator="A", one_c=one_c)


@pytest.mark.asyncio
async def test_add_document_rejects_invalid_barcode(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    from app.exceptions import BarcodeError
    with pytest.raises(BarcodeError):
        await svc.add_document(db_session, envelope=env, barcode="abc", operator="A", one_c=one_c)


@pytest.mark.asyncio
async def test_add_document_duplicate_raises_already_in_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    barcode = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=barcode, operator="A", one_c=one_c)
    await db_session.commit()
    from app.exceptions import DocumentAlreadyInEnvelope
    with pytest.raises(DocumentAlreadyInEnvelope):
        await svc.add_document(db_session, envelope=env, barcode=barcode, operator="A", one_c=one_c)
```

- [ ] **Step 2: Run, expect fail**

Expected: `add_document` missing.

- [ ] **Step 3: Implement `add_document`**

Append to `app/services/envelopes.py`:
```python
from app.exceptions import DocumentAlreadyInEnvelope, EnvelopeNotDraft
from app.models import EnvelopeDocument
from app.services.barcode import doc_barcode_to_guid
from app.services.odata import OneCClient


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

    # Pre-check duplicate (cheap; UNIQUE constraint is the real guard).
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
        payload={"doc_guid": str(guid), "doc_kind": normalized.doc_kind, "doc_number": normalized.doc_number},
    )
    return doc
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py tests/test_envelopes_service.py
git commit -m "feat: add_document service with OData lookup, dup check, audit"
```

---

## Task 18: Envelope service — remove_document

**Files:**
- Modify: `app/services/envelopes.py`
- Modify: `tests/test_envelopes_service.py`

- [ ] **Step 1: Failing tests**

Append:
```python
@pytest.mark.asyncio
async def test_remove_document_happy(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    doc = await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    await db_session.commit()
    await svc.remove_document(db_session, envelope=env, doc_id=doc.id, operator="A")
    await db_session.commit()
    docs = (await db_session.execute(select(EnvelopeDocument))).scalars().all()
    assert docs == []


@pytest.mark.asyncio
async def test_remove_document_when_sealed_raises(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    await db_session.commit()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.remove_document(db_session, envelope=env, doc_id=uuid.uuid4(), operator="A")
```

Add to imports at top of test file: `from app.models import EnvelopeDocument`.

- [ ] **Step 2: Run, expect fail**

Expected: `remove_document` missing.

- [ ] **Step 3: Implement**

Append to `app/services/envelopes.py`:
```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py tests/test_envelopes_service.py
git commit -m "feat: remove_document service (draft only, idempotent)"
```

---

## Task 19: Envelope service — seal

**Files:**
- Modify: `app/services/envelopes.py`
- Modify: `tests/test_envelopes_service.py`

- [ ] **Step 1: Failing tests**

Append:
```python
from app.models import Branch, Signer


async def _make_dictionary(db_session):
    b1 = Branch(name="Москва"); b2 = Branch(name="Казань")
    s1 = Signer(last_name="Иванов", first_name="Иван")
    s2 = Signer(last_name="Петров", first_name="Пётр")
    db_session.add_all([b1, b2, s1, s2])
    await db_session.flush()
    return b1, b2, s1, s2


@pytest.mark.asyncio
async def test_seal_happy(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()

    sealed = await svc.seal(
        db_session, envelope=env,
        signer_sender_id=s1.id, signer_receiver_id=s2.id,
        origin_branch_id=b1.id, destination_branch_id=b2.id,
        notes="хрупкое",
        operator="A",
    )
    await db_session.commit()
    assert sealed.status == EnvelopeStatus.sealed
    assert sealed.sealed_at is not None
    assert sealed.signer_sender_id == s1.id
    assert sealed.notes == "хрупкое"


@pytest.mark.asyncio
async def test_seal_rejects_empty_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()
    from app.exceptions import InvalidSealPayload
    with pytest.raises(InvalidSealPayload):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=b2.id,
                       notes=None, operator="A")


@pytest.mark.asyncio
async def test_seal_rejects_inactive_signer(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    s1.is_active = False
    await db_session.commit()
    from app.exceptions import InvalidSealPayload
    with pytest.raises(InvalidSealPayload):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=b2.id,
                       notes=None, operator="A")


@pytest.mark.asyncio
async def test_seal_already_sealed_raises_not_draft(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=b2.id,
                       notes=None, operator="A")
```

- [ ] **Step 2: Run, expect fail**

Expected: `seal` missing.

- [ ] **Step 3: Implement `seal`**

Append:
```python
from datetime import datetime, timezone

from app.exceptions import InvalidSealPayload
from app.models import Branch, Signer


async def seal(
    session: AsyncSession,
    *,
    envelope: Envelope,
    signer_sender_id: uuid.UUID,
    signer_receiver_id: uuid.UUID,
    origin_branch_id: uuid.UUID,
    destination_branch_id: uuid.UUID,
    notes: str | None,
    operator: str,
) -> Envelope:
    if envelope.status is not EnvelopeStatus.draft:
        raise EnvelopeNotDraft("Конверт уже запечатан")

    if not envelope.documents:
        # `documents` was eagerly loaded (selectin) on the model relationship.
        # In a freshly created envelope used in same session it may not be populated; reload.
        cnt = (await session.execute(
            select(EnvelopeDocument).where(EnvelopeDocument.envelope_id == envelope.id)
        )).scalars().all()
        if not cnt:
            raise InvalidSealPayload("В конверте нет ни одного документа")

    branches = (await session.execute(
        select(Branch).where(Branch.id.in_([origin_branch_id, destination_branch_id]))
    )).scalars().all()
    if len(branches) != 2 or any(not b.is_active for b in branches):
        raise InvalidSealPayload("Указан несуществующий или неактивный филиал")

    signers = (await session.execute(
        select(Signer).where(Signer.id.in_([signer_sender_id, signer_receiver_id]))
    )).scalars().all()
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

    await write_event(session, envelope_id=envelope.id, event="seal", actor=operator,
                      payload={"origin": str(origin_branch_id), "destination": str(destination_branch_id)})
    return envelope
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_envelopes_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/envelopes.py tests/test_envelopes_service.py
git commit -m "feat: seal service validates dictionaries and freezes envelope"
```

---

## Task 20: Verify service — start, scan, finish

**Files:**
- Create: `app/services/verify.py`
- Create: `tests/test_verify_service.py`

- [ ] **Step 1: Failing tests `tests/test_verify_service.py`**

```python
import uuid
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.exceptions import EnvelopeNotDraft, VerificationUnscanned
from app.models import EnvelopeDocument, EnvelopeStatus
from app.services import envelopes as env_svc
from app.services import verify as svc
from app.services.odata import NormalizedDocument


def _norm() -> NormalizedDocument:
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-1",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-1", "Date": "2026-04-20T00:00:00"},
    )


def _bc(guid_str: str) -> str:
    return str(int.from_bytes(uuid.UUID(guid_str).bytes, "big"))


async def _make_sealed(db_session, doc_guids):
    env = await env_svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    for g in doc_guids:
        n = _norm()
        n.doc_number = f"ПЕР-{g[:4]}"
        one_c.lookup_document_with_related.return_value = n
        await env_svc.add_document(db_session, envelope=env, barcode=_bc(g), operator="A", one_c=one_c)
    from app.models import Branch, Signer
    b1, b2 = Branch(name="A"), Branch(name="B")
    s1, s2 = Signer(last_name="X", first_name="x"), Signer(last_name="Y", first_name="y")
    db_session.add_all([b1, b2, s1, s2]); await db_session.flush()
    await env_svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=b2.id, notes=None, operator="A")
    await db_session.commit()
    return env


@pytest.mark.asyncio
async def test_start_writes_verified_by_and_audit(db_session):
    env = await _make_sealed(db_session, ["11111111-1111-1111-1111-111111111111"])
    await svc.start(db_session, envelope=env, operator="Receiver")
    await db_session.commit()
    assert env.verified_by == "Receiver"
    # status stays sealed until finish


@pytest.mark.asyncio
async def test_start_rejects_draft(db_session):
    env = await env_svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    with pytest.raises(EnvelopeNotDraft):  # reused: "envelope must be sealed" — see note
        await svc.start(db_session, envelope=env, operator="X")
```

> Note about the exception: in this plan, `start` rejects an envelope that is **not sealed** (whether draft, verified, or already verified_with_discrepancy). We reuse `EnvelopeNotDraft` only when status is draft; for any other invalid state we raise the same — but with a clarifying detail. Test above only covers the draft path, which is the realistic case.

```python
@pytest.mark.asyncio
async def test_scan_matches_document(db_session):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _make_sealed(db_session, [g])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.scan(db_session, envelope=env, barcode=_bc(g), operator="R")
    await db_session.commit()
    assert res.matched is True
    doc = (await db_session.execute(select(EnvelopeDocument))).scalar_one()
    assert doc.scanned_at_verification is not None


@pytest.mark.asyncio
async def test_scan_unknown_barcode_returns_not_in_envelope(db_session):
    env = await _make_sealed(db_session, ["11111111-1111-1111-1111-111111111111"])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.scan(db_session, envelope=env, barcode="0", operator="R")
    assert res.matched is False
    assert res.reason == "not_in_envelope"


@pytest.mark.asyncio
async def test_finish_all_scanned_marks_verified(db_session):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _make_sealed(db_session, [g])
    await svc.start(db_session, envelope=env, operator="R")
    await svc.scan(db_session, envelope=env, barcode=_bc(g), operator="R")
    await db_session.commit()
    res = await svc.finish(db_session, envelope=env, force=False, operator="R")
    await db_session.commit()
    assert res.status == "verified"
    assert env.status == EnvelopeStatus.verified
    assert env.verified_at is not None


@pytest.mark.asyncio
async def test_finish_unscanned_without_force_raises(db_session):
    env = await _make_sealed(db_session, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    with pytest.raises(VerificationUnscanned):
        await svc.finish(db_session, envelope=env, force=False, operator="R")


@pytest.mark.asyncio
async def test_finish_force_marks_with_discrepancy(db_session):
    env = await _make_sealed(db_session, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.finish(db_session, envelope=env, force=True, operator="R")
    await db_session.commit()
    assert res.status == "verified_with_discrepancy"
    assert len(res.missing_docs) == 2
    assert env.status == EnvelopeStatus.verified_with_discrepancy
```

- [ ] **Step 2: Run, expect fail**

Expected: module missing.

- [ ] **Step 3: Implement `app/services/verify.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_verify_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/verify.py tests/test_verify_service.py
git commit -m "feat: verification service (start, scan, finish)"
```

---

## Task 21: Dictionaries service — branches and signers CRUD

**Files:**
- Create: `app/services/dictionaries.py`
- Create: `tests/test_dictionaries_service.py`

- [ ] **Step 1: Failing test**

```python
import pytest

from app.services import dictionaries as svc
from app.models import Branch, Signer


@pytest.mark.asyncio
async def test_branches_create_list_patch(db_session):
    b = await svc.create_branch(db_session, name="Москва", operator="A")
    await db_session.commit()
    assert b.is_active is True

    listed = await svc.list_branches(db_session, only_active=True)
    assert [x.id for x in listed] == [b.id]

    await svc.patch_branch(db_session, branch_id=b.id, is_active=False, name=None, operator="A")
    await db_session.commit()
    listed_active = await svc.list_branches(db_session, only_active=True)
    assert listed_active == []
    listed_all = await svc.list_branches(db_session, only_active=False)
    assert len(listed_all) == 1


@pytest.mark.asyncio
async def test_signers_create_list_patch(db_session):
    s = await svc.create_signer(db_session, last_name="Иванов", first_name="Иван", operator="A")
    await db_session.commit()
    listed = await svc.list_signers(db_session, only_active=True)
    assert [x.id for x in listed] == [s.id]

    await svc.patch_signer(db_session, signer_id=s.id, last_name="Петров",
                           first_name=None, is_active=None, operator="A")
    await db_session.commit()
    refreshed = (await svc.list_signers(db_session, only_active=True))[0]
    assert refreshed.last_name == "Петров"
```

- [ ] **Step 2: Run, expect fail**

Expected: module missing.

- [ ] **Step 3: Implement `app/services/dictionaries.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Branch, Signer
from app.services.audit import write_event


async def list_branches(session: AsyncSession, *, only_active: bool) -> list[Branch]:
    stmt = select(Branch).order_by(Branch.name)
    if only_active:
        stmt = stmt.where(Branch.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def create_branch(session: AsyncSession, *, name: str, operator: str) -> Branch:
    b = Branch(name=name)
    session.add(b)
    await session.flush()
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "branch", "action": "create", "id": str(b.id), "name": name})
    return b


async def patch_branch(session: AsyncSession, *, branch_id: uuid.UUID,
                       is_active: bool | None, name: str | None, operator: str) -> Branch:
    b = (await session.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    changes = {}
    if is_active is not None:
        b.is_active = is_active
        changes["is_active"] = is_active
    if name is not None:
        b.name = name
        changes["name"] = name
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "branch", "action": "patch", "id": str(b.id), "changes": changes})
    return b


async def list_signers(session: AsyncSession, *, only_active: bool) -> list[Signer]:
    stmt = select(Signer).order_by(Signer.last_name, Signer.first_name)
    if only_active:
        stmt = stmt.where(Signer.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def create_signer(session: AsyncSession, *, last_name: str, first_name: str, operator: str) -> Signer:
    s = Signer(last_name=last_name, first_name=first_name)
    session.add(s)
    await session.flush()
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "signer", "action": "create", "id": str(s.id)})
    return s


async def patch_signer(session: AsyncSession, *, signer_id: uuid.UUID,
                       last_name: str | None, first_name: str | None,
                       is_active: bool | None, operator: str) -> Signer:
    s = (await session.execute(select(Signer).where(Signer.id == signer_id))).scalar_one()
    changes: dict = {}
    if last_name is not None:
        s.last_name = last_name; changes["last_name"] = last_name
    if first_name is not None:
        s.first_name = first_name; changes["first_name"] = first_name
    if is_active is not None:
        s.is_active = is_active; changes["is_active"] = is_active
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "signer", "action": "patch", "id": str(s.id), "changes": changes})
    return s
```

- [ ] **Step 4: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_dictionaries_service.py -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/dictionaries.py tests/test_dictionaries_service.py
git commit -m "feat: dictionaries (branches, signers) CRUD service"
```

---

## Task 22: API router — envelopes (create, get, by-barcode)

**Files:**
- Create: `app/routers/api/envelopes.py`
- Modify: `app/main.py`
- Create: `tests/test_api_envelopes.py`

- [ ] **Step 1: Failing tests `tests/test_api_envelopes.py`**

```python
import pytest


@pytest.mark.asyncio
async def test_post_envelope_requires_operator_cookie(client):
    r = await client.post("/api/envelopes", json={})
    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_post_envelope_creates_draft(client):
    client.cookies.set("operator_name", "Иван")
    r = await client.post("/api/envelopes", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["created_by"] == "Иван"
    assert body["number"].startswith("ТА-")
    assert body["barcode"].isdigit() and len(body["barcode"]) == 16


@pytest.mark.asyncio
async def test_get_envelope_by_id_returns_object(client):
    client.cookies.set("operator_name", "Иван")
    created = (await client.post("/api/envelopes", json={})).json()
    r = await client.get(f"/api/envelopes/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_envelope_by_id_404(client):
    r = await client.get("/api/envelopes/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["code"] == "envelope_not_found"


@pytest.mark.asyncio
async def test_get_envelope_by_barcode(client):
    client.cookies.set("operator_name", "Иван")
    created = (await client.post("/api/envelopes", json={})).json()
    r = await client.get(f"/api/envelopes/by-barcode/{created['barcode']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_envelope_by_barcode_404(client):
    r = await client.get("/api/envelopes/by-barcode/0000000000000000")
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect fail**

Expected: 404 routes.

- [ ] **Step 3: Implement `app/routers/api/envelopes.py`**

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.envelope import EnvelopeOut
from app.services import envelopes as svc

router = APIRouter(prefix="/api/envelopes", tags=["envelopes"])


@router.post("", response_model=EnvelopeOut, status_code=status.HTTP_201_CREATED)
async def create_envelope(
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    env = await svc.create_envelope(session, operator=operator)
    await session.commit()
    return await svc.get_by_id(session, env.id)


@router.get("/{envelope_id}", response_model=EnvelopeOut)
async def get_envelope(envelope_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await svc.get_by_id(session, envelope_id)


@router.get("/by-barcode/{barcode}", response_model=EnvelopeOut)
async def get_envelope_by_barcode(barcode: str, session: AsyncSession = Depends(get_session)):
    return await svc.get_by_barcode(session, barcode)
```

- [ ] **Step 4: Wire in `app/main.py`**

Add import and include:
```python
from app.routers.api import envelopes as envelopes_api  # at top
# ...
app.include_router(envelopes_api.router)
```

- [ ] **Step 5: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_api_envelopes.py -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/api/envelopes.py app/main.py tests/test_api_envelopes.py
git commit -m "feat(api): POST /api/envelopes, GET /{id}, GET by-barcode"
```

---

## Task 23: API router — documents (add, remove)

**Files:**
- Modify: `app/routers/api/envelopes.py`
- Modify: `tests/test_api_envelopes.py`

- [ ] **Step 1: Failing tests**

Append to `tests/test_api_envelopes.py`:
```python
import uuid as _u
from unittest.mock import AsyncMock, patch
from datetime import date as _date
from app.services.odata import NormalizedDocument


def _bc(g: str) -> str:
    return str(int.from_bytes(_u.UUID(g).bytes, "big"))


def _norm():
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-1",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-1", "Date": "2026-04-20T00:00:00"},
    )


@pytest.fixture
def stub_one_c():
    """Replaces the OneCClient on app.dependency_overrides with an AsyncMock."""
    from app.main import app, get_one_c_client
    mock = AsyncMock()
    mock.lookup_document_with_related.return_value = _norm()
    app.dependency_overrides[get_one_c_client] = lambda: mock
    yield mock


@pytest.mark.asyncio
async def test_post_document_adds_doc(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    assert r.status_code == 201
    body = r.json()
    assert body["doc_kind"] == "Перемещение товаров"
    assert body["doc_barcode"] == bc


@pytest.mark.asyncio
async def test_post_document_invalid_barcode(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": "abc"})
    assert r.status_code == 400
    assert r.json()["code"] == "barcode_invalid"


@pytest.mark.asyncio
async def test_post_document_duplicate(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    r = await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    assert r.status_code == 409
    assert r.json()["code"] == "document_already_in_envelope"


@pytest.mark.asyncio
async def test_delete_document(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    doc = (await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})).json()
    r = await client.delete(f"/api/envelopes/{env['id']}/documents/{doc['id']}")
    assert r.status_code == 204
```

- [ ] **Step 2: Run, expect fail**

Expected: 404 (routes not yet defined).

- [ ] **Step 3: Add document routes to `app/routers/api/envelopes.py`**

Append:
```python
from fastapi import Response

from app.main import get_one_c_client  # imported lazily to avoid circular
from app.schemas.document import DocumentAddRequest, DocumentOut
from app.services.odata import OneCClient


@router.post("/{envelope_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def add_document(
    envelope_id: uuid.UUID,
    body: DocumentAddRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
):
    envelope = await svc.get_by_id(session, envelope_id)
    doc = await svc.add_document(session, envelope=envelope, barcode=body.barcode,
                                  operator=operator, one_c=one_c)
    await session.commit()
    return doc


@router.delete("/{envelope_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    envelope_id: uuid.UUID,
    doc_id: uuid.UUID,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    await svc.remove_document(session, envelope=envelope, doc_id=doc_id, operator=operator)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

> Note on circular import: `app.main` imports `app.routers.api.envelopes` at startup; `app.routers.api.envelopes` imports `get_one_c_client` from `app.main`. Move `get_one_c_client` to a new helper module to break the cycle.

- [ ] **Step 4: Break the import cycle**

Create `app/deps.py`:
```python
from app.services.odata import OneCClient


def get_one_c_client() -> OneCClient:
    raise RuntimeError("OneCClient not initialized — lifespan did not run")
```

In `app/main.py` change `def get_one_c_client(...)` definition to `from app.deps import get_one_c_client` (and delete the local stub function); keep the lifespan override of `app.dependency_overrides[get_one_c_client]`.

In `app/routers/api/envelopes.py` change the import:
```python
from app.deps import get_one_c_client
```

In `tests/conftest.py` change the import inside the `client` fixture similarly:
```python
from app.deps import get_one_c_client
```

- [ ] **Step 5: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_api_envelopes.py -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/deps.py app/main.py app/routers/api/envelopes.py tests/conftest.py tests/test_api_envelopes.py
git commit -m "feat(api): add and remove documents on envelope; extract get_one_c_client into deps"
```

---

## Task 24: API router — seal

**Files:**
- Modify: `app/routers/api/envelopes.py`
- Modify: `tests/test_api_envelopes.py`

- [ ] **Step 1: Failing tests**

Append to `tests/test_api_envelopes.py`:
```python
async def _make_dictionary_via_api(client):
    b1 = (await client.post("/api/branches", json={"name": "A"})).json()
    b2 = (await client.post("/api/branches", json={"name": "B"})).json()
    s1 = (await client.post("/api/signers", json={"last_name": "X", "first_name": "x"})).json()
    s2 = (await client.post("/api/signers", json={"last_name": "Y", "first_name": "y"})).json()
    return b1, b2, s1, s2


@pytest.mark.asyncio
async def test_seal_happy(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    b1, b2, s1, s2 = await _make_dictionary_via_api(client)
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"],
        "notes": None,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "sealed"


@pytest.mark.asyncio
async def test_seal_empty_envelope_invalid(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    b1, b2, s1, s2 = await _make_dictionary_via_api(client)
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"],
        "notes": None,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_seal_payload"
```

- [ ] **Step 2: Run, expect fail (404 on seal route + dictionaries also missing)**

We will implement dictionaries in Task 25, but seal route can already be wired here. Note: `_make_dictionary_via_api` uses dictionary endpoints — if Task 25 hasn't been done yet, run only the seal-route-specific test by creating dict rows directly via the DB session. Since we go in order, do this:

Insert a smaller smoke test FIRST that does **not** need dictionary endpoints and lets you implement seal alone:
```python
@pytest.mark.asyncio
async def test_seal_route_returns_400_when_unknown_signer(client, stub_one_c):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    bc = _bc("11111111-1111-1111-1111-111111111111")
    await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": bc})
    fake = "00000000-0000-0000-0000-000000000001"
    r = await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": fake, "signer_receiver_id": fake,
        "origin_branch_id": fake, "destination_branch_id": fake,
        "notes": None,
    })
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_seal_payload"
```

Run: `venv/Scripts/python -m pytest tests/test_api_envelopes.py::test_seal_route_returns_400_when_unknown_signer -x`. Expected: FAIL with 404 (route missing).

The two larger tests (`test_seal_happy`, `test_seal_empty_envelope_invalid`) will start passing only after Task 25.

- [ ] **Step 3: Implement seal route**

Append to `app/routers/api/envelopes.py`:
```python
from app.schemas.envelope import SealRequest


@router.post("/{envelope_id}/seal", response_model=EnvelopeOut)
async def seal_envelope(
    envelope_id: uuid.UUID,
    body: SealRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await svc.get_by_id(session, envelope_id)
    sealed = await svc.seal(
        session, envelope=envelope,
        signer_sender_id=body.signer_sender_id,
        signer_receiver_id=body.signer_receiver_id,
        origin_branch_id=body.origin_branch_id,
        destination_branch_id=body.destination_branch_id,
        notes=body.notes, operator=operator,
    )
    await session.commit()
    return await svc.get_by_id(session, sealed.id)
```

- [ ] **Step 4: Run the small seal test**

Run: `venv/Scripts/python -m pytest tests/test_api_envelopes.py::test_seal_route_returns_400_when_unknown_signer -x`
Expected: PASS. The other two seal tests still fail (no dictionary routes yet).

- [ ] **Step 5: Commit**

```bash
git add app/routers/api/envelopes.py tests/test_api_envelopes.py
git commit -m "feat(api): POST /api/envelopes/{id}/seal"
```

---

## Task 25: API router — dictionaries

**Files:**
- Create: `app/routers/api/dictionaries.py`
- Modify: `app/main.py`
- Create: `tests/test_api_dictionaries.py`

- [ ] **Step 1: Failing tests**

```python
import pytest


@pytest.mark.asyncio
async def test_branches_post_get_patch(client):
    client.cookies.set("operator_name", "Иван")
    r = await client.post("/api/branches", json={"name": "Москва"})
    assert r.status_code == 201
    branch = r.json()
    assert branch["is_active"] is True

    listed = (await client.get("/api/branches?active=true")).json()
    assert any(b["id"] == branch["id"] for b in listed)

    r = await client.patch(f"/api/branches/{branch['id']}", json={"is_active": False})
    assert r.status_code == 200

    listed = (await client.get("/api/branches?active=true")).json()
    assert all(b["id"] != branch["id"] for b in listed)


@pytest.mark.asyncio
async def test_signers_post_get_patch(client):
    client.cookies.set("operator_name", "Иван")
    r = await client.post("/api/signers", json={"last_name": "Иванов", "first_name": "Иван"})
    assert r.status_code == 201
    s = r.json()

    listed = (await client.get("/api/signers?active=true")).json()
    assert any(x["id"] == s["id"] for x in listed)

    r = await client.patch(f"/api/signers/{s['id']}", json={"last_name": "Петров"})
    assert r.status_code == 200
    assert r.json()["last_name"] == "Петров"
```

- [ ] **Step 2: Run, expect fail**

Expected: 404.

- [ ] **Step 3: Implement `app/routers/api/dictionaries.py`**

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.dictionary import (
    BranchCreate, BranchOut, BranchPatch,
    SignerCreate, SignerOut, SignerPatch,
)
from app.services import dictionaries as svc

router = APIRouter(tags=["dictionaries"])


@router.get("/api/branches", response_model=list[BranchOut])
async def list_branches(active: bool = True, session: AsyncSession = Depends(get_session)):
    return await svc.list_branches(session, only_active=active)


@router.post("/api/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: BranchCreate,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    b = await svc.create_branch(session, name=body.name, operator=operator)
    await session.commit()
    return b


@router.patch("/api/branches/{branch_id}", response_model=BranchOut)
async def patch_branch(
    branch_id: uuid.UUID,
    body: BranchPatch,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    b = await svc.patch_branch(session, branch_id=branch_id,
                                is_active=body.is_active, name=body.name, operator=operator)
    await session.commit()
    return b


@router.get("/api/signers", response_model=list[SignerOut])
async def list_signers(active: bool = True, session: AsyncSession = Depends(get_session)):
    return await svc.list_signers(session, only_active=active)


@router.post("/api/signers", response_model=SignerOut, status_code=status.HTTP_201_CREATED)
async def create_signer(
    body: SignerCreate,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    s = await svc.create_signer(session, last_name=body.last_name, first_name=body.first_name,
                                 operator=operator)
    await session.commit()
    return s


@router.patch("/api/signers/{signer_id}", response_model=SignerOut)
async def patch_signer(
    signer_id: uuid.UUID,
    body: SignerPatch,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    s = await svc.patch_signer(session, signer_id=signer_id,
                                last_name=body.last_name, first_name=body.first_name,
                                is_active=body.is_active, operator=operator)
    await session.commit()
    return s
```

- [ ] **Step 4: Wire in `app/main.py`**

```python
from app.routers.api import dictionaries as dictionaries_api
# ...
app.include_router(dictionaries_api.router)
```

- [ ] **Step 5: Run dictionaries tests + the previously failing seal tests**

Run: `venv/Scripts/python -m pytest tests/test_api_dictionaries.py tests/test_api_envelopes.py -x`
Expected: PASS for both files.

- [ ] **Step 6: Commit**

```bash
git add app/routers/api/dictionaries.py app/main.py tests/test_api_dictionaries.py
git commit -m "feat(api): branches and signers CRUD endpoints"
```

---

## Task 26: API router — verify

**Files:**
- Create: `app/routers/api/verify.py`
- Modify: `app/main.py`
- Create: `tests/test_api_verify.py`

- [ ] **Step 1: Failing tests**

```python
import uuid as _u
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest
from app.services.odata import NormalizedDocument


def _bc(g): return str(int.from_bytes(_u.UUID(g).bytes, "big"))
def _norm():
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров", doc_kind="Перемещение товаров",
        doc_number="X", doc_date=_date(2026, 4, 20),
        related_realization_ref=None, raw_payload={"Number": "X", "Date": "2026-04-20T00:00:00"},
    )


@pytest.fixture
def stub_one_c():
    from app.main import app
    from app.deps import get_one_c_client
    mock = AsyncMock()
    mock.lookup_document_with_related.return_value = _norm()
    app.dependency_overrides[get_one_c_client] = lambda: mock
    yield mock


async def _seal_envelope(client, doc_guids):
    client.cookies.set("operator_name", "Иван")
    env = (await client.post("/api/envelopes", json={})).json()
    for g in doc_guids:
        await client.post(f"/api/envelopes/{env['id']}/documents", json={"barcode": _bc(g)})
    b1 = (await client.post("/api/branches", json={"name": "A"})).json()
    b2 = (await client.post("/api/branches", json={"name": "B"})).json()
    s1 = (await client.post("/api/signers", json={"last_name": "X", "first_name": "x"})).json()
    s2 = (await client.post("/api/signers", json={"last_name": "Y", "first_name": "y"})).json()
    await client.post(f"/api/envelopes/{env['id']}/seal", json={
        "signer_sender_id": s1["id"], "signer_receiver_id": s2["id"],
        "origin_branch_id": b1["id"], "destination_branch_id": b2["id"], "notes": None,
    })
    return env


@pytest.mark.asyncio
async def test_verify_full_flow_no_discrepancy(client, stub_one_c):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _seal_envelope(client, [g])
    r = await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    assert r.status_code == 200
    r = await client.post(f"/api/envelopes/{env['id']}/verify/scan", json={"barcode": _bc(g)})
    assert r.status_code == 200
    assert r.json()["matched"] is True
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": False})
    assert r.status_code == 200
    assert r.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_verify_unknown_barcode_returns_not_in_envelope(client, stub_one_c):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _seal_envelope(client, [g])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/scan", json={"barcode": "0"})
    assert r.json()["matched"] is False
    assert r.json()["reason"] == "not_in_envelope"


@pytest.mark.asyncio
async def test_verify_finish_without_force_409(client, stub_one_c):
    env = await _seal_envelope(client, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": False})
    assert r.status_code == 409
    assert r.json()["code"] == "verification_unscanned"


@pytest.mark.asyncio
async def test_verify_finish_force_returns_discrepancy(client, stub_one_c):
    env = await _seal_envelope(client, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await client.post(f"/api/envelopes/{env['id']}/verify/start", json={})
    r = await client.post(f"/api/envelopes/{env['id']}/verify/finish", json={"force": True})
    assert r.status_code == 200
    assert r.json()["status"] == "verified_with_discrepancy"
    assert len(r.json()["missing_docs"]) == 2
```

- [ ] **Step 2: Run, expect fail**

Expected: 404.

- [ ] **Step 3: Implement `app/routers/api/verify.py`**

```python
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.envelope import EnvelopeOut
from app.schemas.verify import (
    VerifyFinishRequest, VerifyFinishResponse, VerifyScanRequest, VerifyScanResponse,
)
from app.services import envelopes as env_svc
from app.services import verify as svc

router = APIRouter(prefix="/api/envelopes", tags=["verify"])


@router.post("/{envelope_id}/verify/start", response_model=EnvelopeOut)
async def verify_start(
    envelope_id: uuid.UUID,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    await svc.start(session, envelope=envelope, operator=operator)
    await session.commit()
    return await env_svc.get_by_id(session, envelope_id)


@router.post("/{envelope_id}/verify/scan", response_model=VerifyScanResponse)
async def verify_scan(
    envelope_id: uuid.UUID,
    body: VerifyScanRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    res = await svc.scan(session, envelope=envelope, barcode=body.barcode, operator=operator)
    await session.commit()
    return VerifyScanResponse(matched=res.matched, doc_id=res.doc_id,
                              scanned_at=res.scanned_at, reason=res.reason)


@router.post("/{envelope_id}/verify/finish", response_model=VerifyFinishResponse)
async def verify_finish(
    envelope_id: uuid.UUID,
    body: VerifyFinishRequest,
    operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    res = await svc.finish(session, envelope=envelope, force=body.force, operator=operator)
    await session.commit()
    return VerifyFinishResponse(status=res.status, missing_docs=res.missing_docs)
```

- [ ] **Step 4: Wire in `app/main.py`**

```python
from app.routers.api import verify as verify_api
# ...
app.include_router(verify_api.router)
```

- [ ] **Step 5: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_api_verify.py -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/api/verify.py app/main.py tests/test_api_verify.py
git commit -m "feat(api): verification endpoints (start, scan, finish)"
```

---

## Task 27: API router — admin reset (dev/test only)

**Files:**
- Create: `app/routers/api/admin.py`
- Modify: `app/main.py`
- Create: `tests/test_api_admin.py`

- [ ] **Step 1: Failing tests `tests/test_api_admin.py`**

```python
import pytest
from sqlalchemy import select

from app.models import Envelope


@pytest.mark.asyncio
async def test_admin_reset_requires_token(client):
    r = await client.post("/api/admin/reset", json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 401
    assert r.json()["code"] == "admin_token_invalid"


@pytest.mark.asyncio
async def test_admin_reset_requires_confirm(client, admin_token):
    r = await client.post("/api/admin/reset",
                           headers={"X-Admin-Token": admin_token}, json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_reset_truncates_envelopes(client, admin_token, db_session):
    client.cookies.set("operator_name", "Иван")
    await client.post("/api/envelopes", json={})
    pre = (await db_session.execute(select(Envelope))).scalars().all()
    assert len(pre) == 1

    r = await client.post(
        "/api/admin/reset",
        headers={"X-Admin-Token": admin_token},
        json={"confirm": "I_KNOW_WHAT_I_DO"},
    )
    assert r.status_code == 200

    post = (await db_session.execute(select(Envelope))).scalars().all()
    assert post == []


@pytest.mark.asyncio
async def test_admin_reset_404_in_production(client, admin_token, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    from app.config import get_settings
    get_settings.cache_clear()
    r = await client.post("/api/admin/reset",
                           headers={"X-Admin-Token": admin_token},
                           json={"confirm": "I_KNOW_WHAT_I_DO"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect fail**

Expected: 404.

- [ ] **Step 3: Implement `app/routers/api/admin.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetRequest(BaseModel):
    confirm: str


@router.post("/reset")
async def admin_reset(
    body: ResetRequest,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    if get_settings().env == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.confirm != "I_KNOW_WHAT_I_DO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm phrase missing")
    for tbl in ("audit_log", "envelope_documents", "envelopes", "signers", "branches"):
        await session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await session.commit()
    return {"reset": True}
```

- [ ] **Step 4: Wire in `app/main.py`**

```python
from app.routers.api import admin as admin_api
# ...
app.include_router(admin_api.router)
```

- [ ] **Step 5: Run, expect pass**

Run: `venv/Scripts/python -m pytest tests/test_api_admin.py -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/api/admin.py app/main.py tests/test_api_admin.py
git commit -m "feat(api): dev-only admin reset endpoint guarded by token + env"
```

---

## Task 28: Final pass — full suite green, README stub

**Files:**
- Create: `README.md` (minimal — full content lives in later plans)

- [ ] **Step 1: Run the entire suite**

Run: `venv/Scripts/python -m pytest -x`
Expected: all green; under 30 seconds total.

- [ ] **Step 2: Smoke-test the running app manually**

In a separate terminal:
```bash
venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```
Then in another shell:
```bash
curl -s http://127.0.0.1:8080/api/health
curl -s -X POST http://127.0.0.1:8080/api/envelopes -H 'cookie: operator_name=ramos' -d '{}'
```
Expected: `{"status":"ok"}`; then a JSON envelope with `status: draft`.

- [ ] **Step 3: Create minimal `README.md`**

```markdown
# Konvert-Trek

Backend service for tracking accounting documents transferred between branches via couriers.

## Status

Foundation + JSON API only. Printing, web UI, and Windows production deployment land in separate plans.

## Quick start (dev)

1. Install Postgres 16 locally; create `convert_track` and `convert_track_test` databases.
2. `python -m venv venv && venv/Scripts/pip install -e ".[dev]"`
3. Copy `.env.example` to `.env` and fill in real OData credentials and an `ADMIN_TOKEN`.
4. `venv/Scripts/python -m alembic upgrade head`
5. `venv/Scripts/python -m uvicorn app.main:app --reload`

API explorer: http://127.0.0.1:8080/docs

## Tests

`venv/Scripts/python -m pytest`

Tests need both `convert_track` (dev) and `convert_track_test` (test) databases reachable at `DATABASE_URL`/`DATABASE_URL_TEST`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: minimal README for backend foundation"
```

---

## Self-review

- **Spec coverage** (vs `docs/superpowers/specs/2026-04-26-konvert-trek-mvp-design.md`):
  - §2 architecture & layout: covered (file map mirrors spec; routers/services/models split; deps module breaks the lifespan/router cycle).
  - §3 data model: all 5 tables + enum + indexes + uniqueness — Tasks 4–5.
  - §4 API: `/api/envelopes` (Tasks 22–24), `/api/envelopes/{id}/verify/*` (Task 26), `/api/branches` and `/api/signers` (Task 25), `/api/admin/reset` (Task 27). `/api/envelopes/{id}/print/*` is **out of scope** for this plan and goes to Plan B.
  - §5 algorithms: barcode→GUID (Task 7), envelope code generator with retry (Tasks 8 + 15), OData type probing + normalization + related lookup (Tasks 11–12), scanner-side logic — out of scope (Plan C).
  - §6 testing: unit (barcode, audit), service (envelopes, verify, dictionaries), API (envelopes, verify, dictionaries, admin), respx for OData. Print and `app.js` testing deferred to later plans.
  - §7 deployment: out of scope (Plan D).
  - §9 risks: addressed where they touch backend — barcode collision retry (Task 15), OData fallback to `OneCUnavailable` (Tasks 11–12), `ENVELOPE_BC_PREFIX` env knob (Task 8), `409 envelope_not_draft` on every mutation post-seal (Tasks 17–19), `verification_unscanned` on incomplete verify (Task 20).
  - §10 not-in-MVP: not implemented; matches spec.

- **Placeholder scan:** No "TBD"/"implement later"/"similar to Task N"/"add appropriate handling" survived. All steps have either runnable commands or full code blocks.

- **Type consistency check:**
  - `NormalizedDocument` definition (Task 12) is consumed unchanged in Tasks 17 + 20 + tests.
  - `OneCClient.lookup_document_with_related` signature (`(guid)` → `NormalizedDocument`) referenced consistently.
  - `EnvelopeStatus` import path `from app.models import EnvelopeStatus` used identically in services and tests.
  - `get_one_c_client` lives in `app/deps.py` from Task 23 onward; both `app/main.py` and tests/conftest.py reference the same import path after Task 23.
  - Service function signatures (`create_envelope`, `add_document`, `remove_document`, `seal`, `start`, `scan`, `finish`) match between services and routers.
  - Pydantic schema names (`EnvelopeOut`, `SealRequest`, `BranchOut`, `BranchCreate`, `BranchPatch`, `SignerOut`, `SignerCreate`, `SignerPatch`, `VerifyScanResponse`, `VerifyFinishResponse`, `DocumentOut`, `DocumentAddRequest`) match between schemas, routers, and tests.

- **Known caveats called out in tasks:**
  - The `EnvelopeNotDraft` exception is reused for "envelope not in sealed state" in `verify.start`/`verify.finish`. Detail string differs; code stays the same. If a finer-grained code is needed later, split into a sibling exception in a follow-up.
  - `OneCClient` is constructed with the real `.env` URL even in the test process. It is fully overridden via `app.dependency_overrides[get_one_c_client]` in `tests/conftest.py`, so no real network calls happen. Smoke-test of OData against the real 1С server is **manual** and out of scope here.
  - Running tests requires a Postgres test DB. The `truncate_tables` autouse fixture does not run migrations — Step 6 of Task 5 does that once.

---

## Follow-up plans (not in this document)

- **Plan B — Printing.** Description PDF (xltpl + soffice headless) and label PDF (ReportLab + Roboto), wired as `/api/envelopes/{id}/print/{description,label}`.
- **Plan C — Web UI.** HTMX-based single page, `app/web/templates/`, `app/web/static/app.js` scanner, full UX from spec §5.4.
- **Plan D — Production deployment.** Dockerfile + docker-compose for dev; nssm install steps; backup task; optional Apache `mod_proxy` config.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-26-konvert-trek-foundation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
