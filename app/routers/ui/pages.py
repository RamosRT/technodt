"""UI routes — renders Jinja2 templates for the single-page HTMX frontend."""
import uuid
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.dictionaries as dict_svc
import app.services.envelopes as env_svc
import app.services.printers as printer_svc
import app.services.system_settings as settings_svc
import app.services.verify as verify_svc
from app.auth import get_is_admin
from app.config import get_settings
from app.db import get_session, get_session_factory
from app.deps import get_one_c_client
from app.exceptions import AppError
from app.models import (
    AuditLog,
    Branch,
    Envelope,
    EnvelopeDocument,
    EnvelopeStatus,
    OneCMarkLog,
    Operator,
    Signer,
)
from app.parsing import optional_query_date
from app.schemas.printer import PrinterCreate, PrinterPatch
from app.services import documents as doc_svc
from app.services import operators as op_svc
from app.services.onec_marks import fire_seal_marks, fire_verify_marks
from app.services.odata import OneCClient

_TMPL_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(_TMPL_DIR))

STATUS_LABELS = {
    "draft": "Черновик",
    "sealed": "Запечатан",
    "verified": "Верифицирован",
    "verified_with_discrepancy": "Расхождение",
}

DOCUMENT_STATUS_LABELS = {
    "verified": "Верифицирован",
    "in_transit": "В пути",
    "missing": "Недостача",
    "draft": "Черновик",
}

router = APIRouter(tags=["ui"])


def _is_bootstrap_admin_name(name: str, admin_login: str) -> bool:
    return bool(admin_login.strip()) and name.strip().casefold() == admin_login.strip().casefold()


def _operator(operator_name: str | None = Cookie(default=None)) -> str | None:
    return unquote(operator_name) if operator_name else None


def _optional_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def _optional_status(value: str | EnvelopeStatus | None) -> EnvelopeStatus | None:
    if value is None or value == "":
        return None
    if isinstance(value, EnvelopeStatus):
        return value
    return EnvelopeStatus(value)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "on", "yes"}


async def _verify_meta(session: AsyncSession, envelope) -> dict:
    branch_name = None
    if envelope.origin_branch_id:
        branch_name = (
            await session.execute(
                select(Branch.name).where(Branch.id == envelope.origin_branch_id)
            )
        ).scalar_one_or_none()

    signer_sender_name = None
    if envelope.signer_sender_id:
        signer_sender_name = (
            await session.execute(
                select(Signer.last_name, Signer.first_name).where(Signer.id == envelope.signer_sender_id)
            )
        ).one_or_none()

    signer_receiver_name = None
    if envelope.signer_receiver_id:
        signer_receiver_name = (
            await session.execute(
                select(Signer.last_name, Signer.first_name).where(Signer.id == envelope.signer_receiver_id)
            )
        ).one_or_none()

    return {
        "origin_branch_name": branch_name,
        "signer_sender_name": (
            f"{signer_sender_name[0]} {signer_sender_name[1]}" if signer_sender_name else None
        ),
        "signer_receiver_name": (
            f"{signer_receiver_name[0]} {signer_receiver_name[1]}" if signer_receiver_name else None
        ),
    }


async def _audit_events(session: AsyncSession, envelope_id: uuid.UUID) -> list[AuditLog]:
    return list(
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.envelope_id == envelope_id)
                .order_by(AuditLog.at.desc())
            )
        ).scalars().all()
    )


async def _audit_screen_context(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    event: str | None = None,
    actor: str | None = None,
    envelope: str | None = None,
) -> dict:
    from datetime import datetime, time, timezone
    from sqlalchemy import or_

    stmt = select(AuditLog).outerjoin(Envelope, AuditLog.envelope_id == Envelope.id)
    if date_from:
        stmt = stmt.where(AuditLog.at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        stmt = stmt.where(AuditLog.at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    if event:
        stmt = stmt.where(AuditLog.event == event)
    if actor:
        stmt = stmt.where(AuditLog.actor.ilike(f"%{actor.strip()}%"))
    if envelope:
        term = f"%{envelope.strip()}%"
        stmt = stmt.where(or_(Envelope.number.ilike(term), Envelope.barcode.ilike(term)))
    events = list((await session.execute(stmt.order_by(AuditLog.at.desc()).limit(50))).scalars().all())
    return {
        "audit_events": events,
        "audit_filters": {
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "event": event or "",
            "actor": actor or "",
            "envelope": envelope or "",
        },
    }


async def _onec_marks_context(
    session: AsyncSession,
    *,
    status: str | None = None,
    doc_number: str | None = None,
    envelope: str | None = None,
) -> dict:
    from sqlalchemy import or_

    stmt = (
        select(
            OneCMarkLog,
            Envelope.number,
            Envelope.barcode,
            EnvelopeDocument.doc_kind,
            EnvelopeDocument.doc_number,
            EnvelopeDocument.doc_date,
        )
        .outerjoin(Envelope, OneCMarkLog.envelope_id == Envelope.id)
        .outerjoin(
            EnvelopeDocument,
            (EnvelopeDocument.envelope_id == OneCMarkLog.envelope_id)
            & (EnvelopeDocument.doc_guid == OneCMarkLog.doc_guid),
        )
    )
    if status == "failed":
        stmt = stmt.where(OneCMarkLog.status == "failed")
    elif status == "success":
        stmt = stmt.where(OneCMarkLog.status == "success")
    if doc_number:
        stmt = stmt.where(EnvelopeDocument.doc_number.ilike(f"%{doc_number.strip()}%"))
    if envelope:
        term = f"%{envelope.strip()}%"
        stmt = stmt.where(or_(Envelope.number.ilike(term), Envelope.barcode.ilike(term)))
    rows = list(
        (
            await session.execute(
                stmt.order_by(OneCMarkLog.attempted_at.desc(), OneCMarkLog.id.desc()).limit(80)
            )
        ).all()
    )
    success_total = (
        await session.execute(
            select(func.count()).select_from(OneCMarkLog).where(OneCMarkLog.status == "success")
        )
    ).scalar_one()
    failed_total = (
        await session.execute(
            select(func.count()).select_from(OneCMarkLog).where(OneCMarkLog.status == "failed")
        )
    ).scalar_one()
    recent_failed = (
        await session.execute(
            select(func.count())
            .select_from(OneCMarkLog)
            .where(
                OneCMarkLog.status == "failed",
                OneCMarkLog.attempted_at >= datetime.combine(
                    datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
                ),
            )
        )
    ).scalar_one()
    mark_rows = [
        {
            "log": log_row,
            "envelope_number": envelope_number,
            "envelope_barcode": envelope_barcode,
            "doc_kind": doc_kind,
            "doc_number": doc_number,
            "doc_date": doc_date,
        }
        for log_row, envelope_number, envelope_barcode, doc_kind, doc_number, doc_date in rows
    ]
    return {
        "onec_mark_rows": mark_rows,
        "onec_mark_stats": {
            "success_total": success_total,
            "failed_total": failed_total,
            "recent_failed": recent_failed,
            "total": success_total + failed_total,
        },
        "onec_mark_filters": {
            "status": status or "",
            "doc_number": doc_number or "",
            "envelope": envelope or "",
        },
    }


async def _envelope_card_context(
    session: AsyncSession,
    *,
    envelope,
    operator: str | None,
    is_admin: bool,
) -> dict:
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)
    return {
        "envelope": envelope,
        "documents": envelope.documents,
        "branches": branches,
        "signers": signers,
        "status_labels": STATUS_LABELS,
        "operator": operator,
        "is_admin": is_admin,
        "audit_events": await _audit_events(session, envelope.id),
    }


def _event_icon(event: str) -> str:
    if event == "verify_finish":
        return "check-circle-2"
    if event in {"add_doc", "create"}:
        return "file-plus-2"
    if event == "seal":
        return "lock"
    if event == "remove_doc":
        return "file-minus-2"
    if event == "verify_scan":
        return "scan-line"
    return "clock-3"


def _event_tone(event: str) -> str:
    if event == "verify_finish":
        return "green"
    if event in {"seal", "verify_scan"}:
        return "blue"
    if event == "remove_doc":
        return "red"
    if event in {"create", "add_doc"}:
        return "amber"
    return "blue"


def _event_title(event: str, payload: dict | None, envelope_number: str | None) -> str:
    payload = payload or {}
    if event == "create":
        return f"Создан конверт {envelope_number or ''}".strip()
    if event == "add_doc":
        doc = payload.get("doc_number") or payload.get("doc_guid") or "документ"
        return f"Добавлен документ {doc}"
    if event == "remove_doc":
        doc = payload.get("doc_number") or payload.get("doc_guid") or "документ"
        return f"Удален документ {doc}"
    if event == "seal":
        return f"Конверт {envelope_number or ''} запечатан".strip()
    if event == "verify_finish":
        return f"Завершена верификация {envelope_number or ''}".strip()
    if event == "verify_scan":
        return f"Отсканирован документ в {envelope_number or 'конверте'}"
    return f"Событие: {event}"


async def _dashboard_context(session: AsyncSession, *, is_admin: bool) -> dict:
    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

    draft_with_docs_subq = (
        select(Envelope.id)
        .join(EnvelopeDocument, EnvelopeDocument.envelope_id == Envelope.id)
        .where(Envelope.status == EnvelopeStatus.draft)
        .group_by(Envelope.id)
        .having(func.count(EnvelopeDocument.id) > 1)
        .subquery()
    )
    new_envelopes_total = (
        await session.execute(select(func.count()).select_from(draft_with_docs_subq))
    ).scalar_one()
    new_envelopes_today = (
        await session.execute(
            select(func.count())
            .select_from(draft_with_docs_subq)
            .join(Envelope, Envelope.id == draft_with_docs_subq.c.id)
            .where(Envelope.created_at >= day_start, Envelope.created_at <= day_end)
        )
    ).scalar_one()

    awaiting_verification_total = (
        await session.execute(
            select(func.count(EnvelopeDocument.id))
            .join(Envelope, Envelope.id == EnvelopeDocument.envelope_id)
            .where(
                Envelope.status == EnvelopeStatus.sealed,
                EnvelopeDocument.scanned_at_verification.is_(None),
            )
        )
    ).scalar_one()

    documents_total = (await session.execute(select(func.count(EnvelopeDocument.id)))).scalar_one()
    documents_today = (
        await session.execute(
            select(func.count(EnvelopeDocument.id))
            .where(
                EnvelopeDocument.added_at >= day_start,
                EnvelopeDocument.added_at <= day_end,
            )
        )
    ).scalar_one()

    discrepancies_total = (
        await session.execute(
            select(func.count(EnvelopeDocument.id))
            .join(Envelope, Envelope.id == EnvelopeDocument.envelope_id)
            .where(
                Envelope.status == EnvelopeStatus.verified_with_discrepancy,
                EnvelopeDocument.scanned_at_verification.is_(None),
            )
        )
    ).scalar_one()

    queue_rows, _ = await env_svc.list_envelopes(
        session,
        status=EnvelopeStatus.sealed,
        page=1,
        page_size=5,
    )
    latest_documents, _, _summary = await doc_svc.list_documents(session, page=1, page_size=5)

    activity_feed: list[dict] = []
    if is_admin:
        activity_rows = list(
            (
                await session.execute(
                    select(AuditLog, Envelope.number)
                    .outerjoin(Envelope, Envelope.id == AuditLog.envelope_id)
                    .order_by(AuditLog.at.desc())
                    .limit(5)
                )
            ).all()
        )
        for ev, envelope_number in activity_rows:
            activity_feed.append(
                {
                    "title": _event_title(ev.event, ev.payload, envelope_number),
                    "actor": ev.actor,
                    "time": ev.at,
                    "icon": _event_icon(ev.event),
                    "tone": _event_tone(ev.event),
                }
            )

    total_envelopes = (await session.execute(select(func.count(Envelope.id)))).scalar_one()
    total_operators = (await session.execute(select(func.count(Operator.id)))).scalar_one()
    return {
        "dashboard": {
            "new_envelopes_total": new_envelopes_total,
            "new_envelopes_today": new_envelopes_today,
            "awaiting_verification_total": awaiting_verification_total,
            "documents_total": documents_total,
            "documents_today": documents_today,
            "discrepancies_total": discrepancies_total,
            "queue_rows": queue_rows,
            "latest_documents": latest_documents,
            "activity_feed": activity_feed,
            "status_labels": STATUS_LABELS,
            "doc_status_labels": DOCUMENT_STATUS_LABELS,
            "total_envelopes": total_envelopes,
            "total_operators": total_operators,
            "server_time": now,
        }
    }


# ─── Root ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
    session: AsyncSession = Depends(get_session),
):
    context = {"operator": operator, "is_admin": is_admin}
    if operator:
        context.update(await _dashboard_context(session, is_admin=is_admin))
    return templates.TemplateResponse(request, "index.html", context)


# ─── Operator ────────────────────────────────────────────────────────────────

@router.post("/ui/operator", response_class=HTMLResponse)
async def set_operator(
    request: Request,
    username: str = Form(default=""),
    operator_name: str = Form(default=""),
    password: str = Form(default=""),
    session: AsyncSession = Depends(get_session),
):
    name = (username or operator_name).strip()
    if not name:
        return HTMLResponse(
            '<div class="alert alert-error">Введите логин</div>',
            status_code=400,
        )
    if len(password) != 4 or not password.isdigit():
        return HTMLResponse(
            '<div class="alert alert-error">Введите PIN из 4 цифр</div>',
            status_code=400,
        )
    settings = get_settings()
    if _is_bootstrap_admin_name(name, settings.admin_login):
        op = await op_svc.ensure_operator(
            session,
            name,
            bootstrap=True,
            password=settings.admin_password if settings.admin_password else None,
        )
        if not op_svc.verify_password(password, op.password_hash):
            return HTMLResponse(
                '<div class="alert alert-error">Неверный логин или пароль</div>',
                status_code=401,
            )
    else:
        op = await op_svc.authenticate_operator(session, name, password)
        if op is None:
            return HTMLResponse(
                '<div class="alert alert-error">Неверный логин или пароль</div>',
                status_code=401,
            )
    await session.commit()
    response = HTMLResponse(status_code=204)
    response.headers["HX-Refresh"] = "true"
    response.set_cookie("operator_name", quote(name), httponly=True, samesite="lax")
    return response


@router.post("/ui/operator/clear", response_class=HTMLResponse)
async def clear_operator(request: Request):
    response = HTMLResponse(status_code=204)
    response.headers["HX-Refresh"] = "true"
    response.delete_cookie("operator_name")
    return response


# ─── Register mode — create envelope ─────────────────────────────────────────

@router.post("/ui/envelopes", response_class=HTMLResponse)
async def ui_create_envelope(
    request: Request,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')

    envelope = await env_svc.create_envelope(session, operator=operator)
    await session.commit()
    envelope = await env_svc.get_by_id(session, envelope.id)
    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


@router.get("/ui/envelopes", response_class=HTMLResponse)
async def ui_envelopes_list(
    request: Request,
    status: str | None = None,
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    branch_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    status_value = _optional_status(status)
    branch_uuid = _optional_uuid(branch_id)
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    envelopes, total = await env_svc.list_envelopes(
        session,
        status=status_value,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_uuid,
        search=search,
        page=page,
    )
    branches = await dict_svc.list_branches(session, only_active=True)
    return templates.TemplateResponse(
        request,
        "partials/envelopes_list.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "envelopes": envelopes,
            "total": total,
            "page": page,
            "page_size": 25,
            "branches": branches,
            "filters": {
                "status": status_value.value if status_value else "",
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
                "branch_id": str(branch_uuid) if branch_uuid else "",
                "search": search or "",
            },
            "status_labels": STATUS_LABELS,
        },
    )


@router.get("/ui/envelopes/{envelope_id}/card", response_class=HTMLResponse)
async def ui_envelope_card(
    request: Request,
    envelope_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    envelope = await env_svc.get_by_id(session, envelope_id)
    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


# ─── Add document ─────────────────────────────────────────────────────────────

@router.post("/ui/envelopes/{envelope_id}/documents", response_class=HTMLResponse)
async def ui_add_document(
    request: Request,
    envelope_id: uuid.UUID,
    barcode: str = Form(...),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.add_document(session, envelope=envelope, barcode=barcode, one_c=one_c, operator=operator)
        await session.commit()
        await session.refresh(envelope, attribute_names=["documents"])
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


# ─── Remove document ──────────────────────────────────────────────────────────

@router.delete("/ui/envelopes/{envelope_id}/documents/{doc_id}", response_class=HTMLResponse)
async def ui_remove_document(
    request: Request,
    envelope_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.remove_document(session, envelope=envelope, doc_id=doc_id, operator=operator)
        await session.commit()
        await session.refresh(envelope, attribute_names=["documents"])
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


# ─── Seal ─────────────────────────────────────────────────────────────────────

@router.post("/ui/envelopes/{envelope_id}/seal", response_class=HTMLResponse)
async def ui_seal_envelope(
    request: Request,
    envelope_id: uuid.UUID,
    signer_sender_id: uuid.UUID = Form(...),
    signer_receiver_id: uuid.UUID = Form(...),
    origin_branch_id: uuid.UUID = Form(...),
    destination_branch_id: uuid.UUID | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.seal(
            session,
            envelope=envelope,
            signer_sender_id=signer_sender_id,
            signer_receiver_id=signer_receiver_id,
            origin_branch_id=origin_branch_id,
            destination_branch_id=destination_branch_id,
            notes=notes or None,
            operator=operator,
        )
        await session.commit()
        enable_marks = await settings_svc.is_1c_timestamps_enabled(session)
        envelope = await env_svc.get_by_id(session, envelope_id)
        if envelope.sealed_at is not None:
            fire_seal_marks(
                one_c,
                envelope.id,
                list(envelope.documents),
                envelope.sealed_at,
                get_session_factory(),
                enabled=enable_marks,
            )
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


@router.post("/ui/envelopes/{envelope_id}/unseal", response_class=HTMLResponse)
async def ui_unseal_envelope(
    request: Request,
    envelope_id: uuid.UUID,
    reason: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.unseal(session, envelope=envelope, reason=reason, operator=operator or "unknown")
        await session.commit()
        envelope = await env_svc.get_by_id(session, envelope_id)
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)
    return templates.TemplateResponse(
        request,
        "partials/envelope_card.html",
        await _envelope_card_context(session, envelope=envelope, operator=operator, is_admin=is_admin),
    )


@router.get("/ui/documents", response_class=HTMLResponse)
async def ui_documents_list(
    request: Request,
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    doc_kind: str | None = None,
    status: str | None = None,
    branch_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    branch_uuid = _optional_uuid(branch_id)
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    documents, total, summary = await doc_svc.list_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        doc_kind=doc_kind,
        status=status,
        branch_id=branch_uuid,
        search=search,
        page=page,
    )
    branches = await dict_svc.list_branches(session, only_active=True)
    return templates.TemplateResponse(
        request,
        "partials/documents_list.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "documents": documents,
            "total": total,
            "summary": summary,
            "page": page,
            "page_size": 50,
            "branches": branches,
            "filters": {
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
                "doc_kind": doc_kind or "",
                "status": status or "",
                "branch_id": str(branch_uuid) if branch_uuid else "",
                "search": search or "",
            },
        },
    )


# ─── Verify mode ──────────────────────────────────────────────────────────────

@router.get("/ui/verify", response_class=HTMLResponse)
async def ui_verify_prompt(request: Request):
    return templates.TemplateResponse(request, "partials/verify_prompt.html", {})


@router.get("/ui/verify/start-by-barcode", response_class=HTMLResponse)
async def ui_verify_start_by_barcode(
    request: Request,
    barcode: str,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_barcode(session, barcode)
        if envelope.status in {EnvelopeStatus.verified, EnvelopeStatus.verified_with_discrepancy}:
            return templates.TemplateResponse(
                request,
                "partials/verify_prompt.html",
                {"error": "Этот конверт уже проверен. Повторная верификация недоступна."},
            )
        await verify_svc.start(session, envelope=envelope, operator=operator)
        await session.commit()
        envelope = await env_svc.get_by_id(session, envelope.id)
    except AppError as e:
        return templates.TemplateResponse(request, "partials/verify_prompt.html", {"error": e.detail})

    scanned = sum(1 for d in envelope.documents if d.scanned_at_verification)
    meta = await _verify_meta(session, envelope)
    return templates.TemplateResponse(request, "partials/verify_card.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "scanned_count": scanned,
        "all_scanned": scanned == len(envelope.documents),
        **meta,
    })


@router.post("/ui/envelopes/{envelope_id}/verify/scan", response_class=HTMLResponse)
async def ui_verify_scan(
    request: Request,
    envelope_id: uuid.UUID,
    barcode: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')

    envelope = await env_svc.get_by_id(session, envelope_id)
    result = await verify_svc.scan(session, envelope=envelope, barcode=barcode, operator=operator)
    await session.commit()
    envelope = await env_svc.get_by_id(session, envelope_id)

    just_scanned_id = result.doc_id if result.matched else None
    for doc in envelope.documents:
        doc.just_scanned = (doc.id == just_scanned_id)

    scanned = sum(1 for d in envelope.documents if d.scanned_at_verification)
    warning = None
    if result.reason == "not_in_envelope":
        warning = "Документ не найден в составе этого конверта"
    elif result.reason == "already_scanned":
        warning = "Этот документ уже был отсканирован в текущей проверке"

    meta = await _verify_meta(session, envelope)
    return templates.TemplateResponse(request, "partials/verify_card.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "scanned_count": scanned,
        "all_scanned": scanned == len(envelope.documents),
        "scan_warning": warning,
        **meta,
    })


@router.post("/ui/envelopes/{envelope_id}/verify/finish", response_class=HTMLResponse)
async def ui_verify_finish(
    request: Request,
    envelope_id: uuid.UUID,
    force: str = Form(default="false"),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')

    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        docs = list(envelope.documents)
        result = await verify_svc.finish(
            session, envelope=envelope, force=(force == "true"), operator=operator
        )
        await session.commit()
        enable_marks = await settings_svc.is_1c_timestamps_enabled(session)
        envelope = await env_svc.get_by_id(session, envelope_id)
        if envelope.verified_at is not None:
            fire_verify_marks(
                one_c,
                envelope.id,
                docs,
                envelope.verified_at,
                get_session_factory(),
                enabled=enable_marks,
            )
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(request, "partials/verify_done.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "missing_count": len(result.missing_docs),
    })


# ─── Admin / dictionaries ─────────────────────────────────────────────────────

async def _admin_ctx(session: AsyncSession, *, is_admin: bool = False) -> dict:
    return {
        "branches": await dict_svc.list_branches(session, only_active=True),
        "signers": await dict_svc.list_signers(session, only_active=True),
        "is_admin": is_admin,
    }


@router.get("/ui/dictionaries", response_class=HTMLResponse)
async def ui_dictionaries(
    request: Request,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="branches")


@router.get("/ui/admin", response_class=HTMLResponse)
async def ui_admin(
    request: Request,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    operators = await op_svc.list_operators(session)
    printers = await printer_svc.list_printers(session, active_only=False)
    audit_ctx = await _audit_screen_context(session)
    onec_marks_ctx = await _onec_marks_context(session)
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)
    enable_1c_timestamps = await settings_svc.is_1c_timestamps_enabled(session)
    return templates.TemplateResponse(
        request,
        "partials/admin_v2.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "operators": operators,
            "printers": printers,
            "branches": branches,
            "signers": signers,
            "enable_1c_timestamps": enable_1c_timestamps,
            "show_reset": get_settings().env != "production",
            "active_admin_tab": "printers",
            **audit_ctx,
            **onec_marks_ctx,
        },
    )


async def _admin_v2_response(
    request: Request,
    session: AsyncSession,
    *,
    operator: str | None,
    is_admin: bool,
    active_tab: str = "printers",
):
    operators = await op_svc.list_operators(session)
    printers = await printer_svc.list_printers(session, active_only=False)
    audit_ctx = await _audit_screen_context(session)
    onec_marks_ctx = await _onec_marks_context(session)
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)
    enable_1c_timestamps = await settings_svc.is_1c_timestamps_enabled(session)
    return templates.TemplateResponse(
        request,
        "partials/admin_v2.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "operators": operators,
            "printers": printers,
            "branches": branches,
            "signers": signers,
            "enable_1c_timestamps": enable_1c_timestamps,
            "show_reset": get_settings().env != "production",
            "active_admin_tab": active_tab,
            **audit_ctx,
            **onec_marks_ctx,
        },
    )


@router.get("/ui/onec-marks", response_class=HTMLResponse)
async def ui_onec_marks(
    request: Request,
    status: str | None = None,
    doc_number: str | None = None,
    envelope: str | None = None,
    session: AsyncSession = Depends(get_session),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    return templates.TemplateResponse(
        request,
        "partials/onec_marks_panel.html",
        await _onec_marks_context(
            session,
            status=status or None,
            doc_number=doc_number or None,
            envelope=envelope or None,
        ),
    )


@router.get("/ui/audit", response_class=HTMLResponse)
async def ui_audit(
    request: Request,
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    event: str | None = None,
    actor: str | None = None,
    envelope: str | None = None,
    session: AsyncSession = Depends(get_session),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    return templates.TemplateResponse(
        request,
        "partials/audit_panel.html",
        await _audit_screen_context(
            session,
            date_from=date_from,
            date_to=date_to,
            event=event or None,
            actor=actor or None,
            envelope=envelope or None,
        ),
    )


@router.post("/ui/operators", response_class=HTMLResponse)
async def ui_create_operator(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    assigned_zpl_printer_id: str = Form(default=""),
    assigned_a4_printer_id: str = Form(default=""),
    is_admin_form: str = Form(default="", alias="is_admin"),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    if len(password) != 4 or not password.isdigit():
        return HTMLResponse(
            '<div class="alert alert-error">Пароль должен быть кодом из 4 цифр</div>',
            status_code=400,
        )
    await op_svc.ensure_operator(
        session,
        username,
        bootstrap=(is_admin_form == "true"),
        password=password,
        assigned_zpl_printer_id=assigned_zpl_printer_id or None,
        assigned_a4_printer_id=assigned_a4_printer_id or None,
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.patch("/ui/operators/{operator_id}", response_class=HTMLResponse)
async def ui_patch_operator(
    request: Request,
    operator_id: uuid.UUID,
    is_admin_form: str = Form(default="", alias="is_admin"),
    is_active: str = Form(default=""),
    password: str = Form(default=""),
    assigned_zpl_printer_id: str = Form(default=""),
    assigned_a4_printer_id: str = Form(default=""),
    delete_form: str = Form(default="", alias="delete"),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    target = (
        await session.execute(select(op_svc.Operator).where(op_svc.Operator.id == operator_id))
    ).scalar_one_or_none()
    if target and target.username == operator and is_active == "false":
        return HTMLResponse(
            '<div class="alert alert-error">Нельзя деактивировать себя</div>',
            status_code=400,
        )
    if target and target.username == operator and is_admin_form == "false":
        return HTMLResponse(
            '<div class="alert alert-error">Нельзя снять роль администратора у себя</div>',
            status_code=400,
        )
    if _is_truthy(delete_form):
        if target is None:
            return HTMLResponse('<div class="alert alert-error">Оператор не найден</div>', status_code=404)
        if target.username == operator:
            return HTMLResponse(
                '<div class="alert alert-error">Нельзя удалить себя</div>',
                status_code=400,
            )
        await op_svc.delete_operator(session, operator_id=operator_id)
        await session.commit()
        return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)
    if password and (len(password) != 4 or not password.isdigit()):
        return HTMLResponse(
            '<div class="alert alert-error">Пароль должен быть кодом из 4 цифр</div>',
            status_code=400,
        )
    await op_svc.patch_operator(
        session,
        operator_id=operator_id,
        is_admin=True if is_admin_form == "true" else (False if is_admin_form == "false" else None),
        is_active=True if is_active == "true" else (False if is_active == "false" else None),
        password=password if password else None,
        assigned_zpl_printer_id=assigned_zpl_printer_id if assigned_zpl_printer_id else None,
        assigned_a4_printer_id=assigned_a4_printer_id if assigned_a4_printer_id else None,
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.get("/ui/settings-drawer", response_class=HTMLResponse)
async def ui_settings_drawer(
    request: Request,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>', status_code=401)
    op = (await session.execute(select(Operator).where(Operator.username == operator))).scalar_one_or_none()
    printers = await printer_svc.list_printers(session, active_only=True)
    return templates.TemplateResponse(
        request,
        "partials/settings_drawer.html",
        {
            "operator": operator,
            "operator_row": op,
            "is_admin": is_admin,
            "branches": await dict_svc.list_branches(session, only_active=True),
            "signers": await dict_svc.list_signers(session, only_active=True),
            "printers": printers,
            "enable_1c_timestamps": await settings_svc.is_1c_timestamps_enabled(session),
        },
    )


@router.patch("/ui/settings", response_class=HTMLResponse)
async def ui_patch_settings(
    request: Request,
    assigned_zpl_printer_id: str = Form(default=""),
    assigned_a4_printer_id: str = Form(default=""),
    default_branch_id: str = Form(default=""),
    default_signer_sender_id: str = Form(default=""),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>', status_code=401)
    await op_svc.patch_operator_settings(
        session,
        username=operator,
        zpl_printer_id=assigned_zpl_printer_id or None,
        a4_printer_id=assigned_a4_printer_id or None,
        default_branch_id=_optional_uuid(default_branch_id),
        default_signer_sender_id=_optional_uuid(default_signer_sender_id),
    )
    await session.commit()
    return await ui_settings_drawer(request, session=session, operator=operator, is_admin=is_admin)


@router.post("/ui/admin/printers", response_class=HTMLResponse)
async def ui_admin_create_printer(
    request: Request,
    id: str = Form(...),
    name: str = Form(...),
    kind: str = Form(...),
    host: str = Form(default=""),
    port: str = Form(default=""),
    dpi: str = Form(default=""),
    share_name: str = Form(default=""),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    data = PrinterCreate(
        id=id.strip(),
        name=name.strip(),
        kind=kind,  # type: ignore[arg-type]
        host=host.strip() or None,
        port=int(port) if port.strip().isdigit() else None,
        dpi=int(dpi) if dpi.strip().isdigit() else None,
        share_name=share_name.strip() or (host.strip() if kind == "a4" else None),
    )
    await printer_svc.create_printer(session, data)
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.patch("/ui/admin/printers/{printer_id}/toggle", response_class=HTMLResponse)
async def ui_admin_toggle_printer(
    request: Request,
    printer_id: str,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    printer = await printer_svc.get_printer(session, printer_id)
    await printer_svc.patch_printer(session, printer_id, PrinterPatch(is_active=not printer.is_active))
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.post("/ui/admin/printers/{printer_id}/delete", response_class=HTMLResponse)
async def ui_admin_delete_printer(
    request: Request,
    printer_id: str,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await printer_svc.delete_printer(session, printer_id)
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.patch("/ui/admin/settings/1c-timestamps", response_class=HTMLResponse)
async def ui_admin_toggle_1c_timestamps(
    request: Request,
    enabled: str = Form(default="false"),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await settings_svc.set_1c_timestamps_enabled(session, _is_truthy(enabled))
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="system")


@router.delete("/ui/operators/{operator_id}", response_class=HTMLResponse)
async def ui_delete_operator(
    request: Request,
    operator_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    target = (
        await session.execute(select(op_svc.Operator).where(op_svc.Operator.id == operator_id))
    ).scalar_one_or_none()
    if target is None:
        return HTMLResponse('<div class="alert alert-error">Оператор не найден</div>', status_code=404)
    if target.username == operator:
        return HTMLResponse(
            '<div class="alert alert-error">Нельзя удалить себя</div>',
            status_code=400,
        )
    await op_svc.delete_operator(session, operator_id=operator_id)
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.post("/ui/operators/{operator_id}/delete", response_class=HTMLResponse)
async def ui_delete_operator_post(
    request: Request,
    operator_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    target = (
        await session.execute(select(op_svc.Operator).where(op_svc.Operator.id == operator_id))
    ).scalar_one_or_none()
    if target is None:
        return HTMLResponse('<div class="alert alert-error">Оператор не найден</div>', status_code=404)
    if target.username == operator:
        return HTMLResponse(
            '<div class="alert alert-error">Нельзя удалить себя</div>',
            status_code=400,
        )
    await op_svc.delete_operator(session, operator_id=operator_id)
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


@router.post("/ui/admin/reset", response_class=HTMLResponse)
async def ui_admin_reset(
    confirm: str = Form(...),
    session: AsyncSession = Depends(get_session),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    if get_settings().env == "production":
        return HTMLResponse('<div class="alert alert-error">Недоступно в production</div>', status_code=404)
    if confirm != "I_KNOW_WHAT_I_DO":
        return HTMLResponse('<div class="alert alert-error">Неверное кодовое слово</div>', status_code=400)
    for tbl in ("onec_mark_logs", "audit_log", "envelope_documents", "envelopes", "signers", "branches"):
        await session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await session.commit()
    return HTMLResponse(
        '<div class="card text-center"><h2>База данных очищена</h2>'
        '<p class="text-muted">Страница обновится автоматически.</p>'
        '<script>setTimeout(()=>location.reload(),1800)</script></div>'
    )


@router.post("/ui/admin/branches", response_class=HTMLResponse)
async def ui_create_branch(
    request: Request,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.create_branch(session, name=name, operator=operator or "ui")
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="branches")


@router.patch("/ui/admin/branches/{branch_id}", response_class=HTMLResponse)
async def ui_patch_branch(
    request: Request,
    branch_id: uuid.UUID,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.patch_branch(session, branch_id=branch_id, name=name, is_active=None, operator=operator or "ui")
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="branches")


@router.post("/ui/admin/branches/{branch_id}/deactivate", response_class=HTMLResponse)
async def ui_deactivate_branch(
    request: Request,
    branch_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.patch_branch(
        session, branch_id=branch_id, name=None, is_active=False, operator=operator or "ui"
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="branches")


@router.post("/ui/admin/signers", response_class=HTMLResponse)
async def ui_create_signer(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.create_signer(
        session, last_name=last_name, first_name=first_name, operator=operator or "ui"
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="signers")


@router.patch("/ui/admin/signers/{signer_id}", response_class=HTMLResponse)
async def ui_patch_signer(
    request: Request,
    signer_id: uuid.UUID,
    last_name: str = Form(...),
    first_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.patch_signer(
        session, signer_id=signer_id, last_name=last_name, first_name=first_name,
        is_active=None, operator=operator or "ui"
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="signers")


@router.post("/ui/admin/signers/{signer_id}/deactivate", response_class=HTMLResponse)
async def ui_deactivate_signer(
    request: Request,
    signer_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    if not is_admin:
        return HTMLResponse('<div class="alert alert-error">Нет прав администратора</div>', status_code=403)
    await dict_svc.patch_signer(
        session, signer_id=signer_id, last_name=None, first_name=None, is_active=False, operator=operator or "ui"
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin, active_tab="signers")
