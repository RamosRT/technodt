# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Greenfield. As of this writing the repo contains **only design documents** — no application code, no `pyproject.toml`, no Alembic config, no migrations. The intent is captured in:

- `development.md` — original problem statement (Russian).
- `project-overview.md` — full architecture, data model, API draft, roadmap (Russian). **Treat this as the source of truth for design decisions.** When implementing, consult it before inventing structure.
- `odata_metadata.xml` — frozen 1C OData EDMX metadata (~179k lines) used to know which `Document_*` entities and properties are available without hitting the live 1C server.

User-facing UI text and printed forms are in Russian. Code identifiers, comments, and commit messages should stay in English; do not translate domain terms in the design docs (`конверт`, `опись`, `УПД`, `УКД` etc.) — they are the canonical names.

## What the system does

"Конверт-трек" (envelope-track): tracks accounting documents physically transferred between branches via couriers. Each document already has a unique barcode printed from 1C. Operators scan documents into a virtual **envelope** (its own barcode + number), seal it, print a paper inventory + barcode label, and on receipt scan the envelope and its contents to detect missing documents.

Two clients hit the same backend:
1. **Web client** on a Windows PC with a barcode scanner in keyboard-emulation mode (terminator = Enter; the scanned input goes into a hidden focused input).
2. **Android TSD app** (Kotlin + Jetpack Compose) using DataWedge/Intent API for scanning. Planned for a later milestone.

## Target stack & deployment

| Layer    | Choice                                                                |
| -------- | --------------------------------------------------------------------- |
| Backend  | Python 3.14 + FastAPI + SQLAlchemy + Alembic (async)                  |
| DB       | PostgreSQL 16                                                         |
| Web UI   | Single static HTML page served by FastAPI; vanilla JS or HTMX. **Do not introduce SPA frameworks** — only one screen. |
| Print    | Jinja2 → HTML → PDF via WeasyPrint for the A4 inventory; ZPL/TSPL direct-to-printer for thermal labels (Code128, ~58×40 mm) |
| Run      | uvicorn as a Windows service via **nssm** on the Windows Server host  |

Server already has Python 3.14, PostgreSQL 16, and Apache (Apache is reserved for publishing 1C — do **not** route the new app through Apache config; if external exposure is needed, use `mod_proxy` to `127.0.0.1:8080`). Plan virtualenv at `E:\technodt\venv`.

## Critical algorithms / non-obvious facts

**Barcode → 1C GUID conversion** (every document add path uses this):
```python
import uuid
def barcode_to_guid(barcode: str) -> str:
    return str(uuid.UUID(bytes=int(barcode).to_bytes(16, "big")))
```
Validate: must be all-digits and fit in 16 bytes; otherwise reject in UI as "ШК не похож на штрихкод документа 1С".

**OData document lookup is type-blind.** The barcode gives a GUID but not a document type, so probe known types in order until one returns 200. Currently in scope:
- `Document_ПеремещениеТоваров`
- `Document_СчетФактураВыданный`

(UPD/UKD are mentioned in the spec but the active whitelist is the two above — confirm before adding more.) Endpoint shape: `GET {ODATA_BASE_URL}/Document_<Type>(guid'<GUID>')?$format=json`.

**Cache the full OData payload** into `envelope_documents.raw_1c_payload` (jsonb) at add-time so envelopes remain self-describing if 1C is later unavailable.

**Envelope number/barcode generator:** prefix `ТА-` followed by random digits, uniqueness enforced via DB constraint + retry on collision. Format must encode as Code128 on the thermal label.

**Status machine:** `draft → sealed → verified | verified_with_discrepancy`. Editing the document list is allowed only while `draft`; once `sealed`, the composition is frozen — enforce server-side, not just in UI.

**Keyboard-mode scanner UX:** the page must keep focus on a hidden input; clicks anywhere else should bounce focus back. Distinguish "document barcode" from "envelope barcode" during sealing either by an explicit "waiting for envelope BC" mode or by prefix/length check.

## Data model anchors

Three tables (full schema in `project-overview.md` §4):
- `envelopes` — uuid PK, unique `barcode`, status enum, sealed/verified timestamps, sender/receiver branches.
- `envelope_documents` — FK to envelope, `doc_barcode`, `doc_guid`, type/number/date pulled from 1C, `raw_1c_payload jsonb`, `scanned_at_verification`.
- `audit_log` — bigserial, every state change (`create`, `add_doc`, `remove_doc`, `seal`, `verify_*`, `reset`) with jsonb payload + actor.

Indexes worth creating up front: `envelopes.barcode` unique, `envelope_documents.envelope_id`, `envelope_documents.doc_barcode` (to answer "in which envelope is this doc?").

## API surface (draft — see §7 of project-overview.md)

Routes are versionless under `/api/...`. Notable shapes:
- `POST /api/envelopes` returns `{id, number, barcode}` for a new draft.
- `GET /api/envelopes/by-barcode/{barcode}` is the verification entry point.
- `POST /api/envelopes/{id}/verify/finish` accepts `force=true` to close with discrepancy.
- `POST /api/admin/reset` is dev/test only — never expose in prod, gate behind admin role + confirmation.
- Print endpoints return `application/pdf` (inventory) or `application/octet-stream` (ZPL).

## Configuration

`.env` at repo root (already present, contains real OData credentials — **do not commit**, do not paste into chat). Required keys:
- `ODATA_BASE_URL` — root of the 1C OData service (the existing value points at the prod 1C base; trailing path is `/odata/standard.odata`).
- `ODATA_ADMIN_USER`, `ODATA_PASSWORD` — read-only technical 1C account.
- `ODATA_TIMEOUT_SECONDS` — default 60.

Add a `.env.example` (sanitized) when the backend skeleton is created, and add `.env` to `.gitignore` in the same commit.

## Build / run / test

No tooling exists yet. When bootstrapping the backend:

```bash
python -m venv venv
venv/Scripts/python -m pip install -e .[dev]   # once pyproject.toml exists
venv/Scripts/python -m alembic upgrade head
venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Production install via nssm (from `project-overview.md` §9):
```
nssm install ConvertTrack "E:\technodt\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 127.0.0.1 --port 8080"
nssm set ConvertTrack AppDirectory E:\technodt
nssm start ConvertTrack
```

Run a single test once pytest is wired: `venv/Scripts/python -m pytest path/to/test_file.py::test_name -x`.

## Things to know before changing scope

- **Reset endpoint** (`/api/admin/reset`) is intentionally dev/test only — confirmed in §12 of `project-overview.md`. Do not promote it to a production feature.
- **Branch / forwarder directory** lives in this app's DB, not in 1C. Do not try to fetch it via OData.
- **Offline mode for the TSD** is explicitly out of MVP scope; design data model to allow it later but do not build the queue now.
- **Apache is not yours.** It serves 1C. Don't add Python handlers to its config.
