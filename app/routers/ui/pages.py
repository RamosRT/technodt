"""UI routes — renders Jinja2 templates for the single-page HTMX frontend."""
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.dictionaries as dict_svc
import app.services.envelopes as env_svc
import app.services.printers as printer_svc
import app.services.verify as verify_svc
from app.auth import get_is_admin
from app.config import get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.exceptions import AppError
from app.models import AuditLog, Branch, Envelope, EnvelopeStatus, Signer
from app.parsing import optional_query_date
from app.services import documents as doc_svc
from app.services import operators as op_svc
from app.services.odata import OneCClient

_TMPL_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(_TMPL_DIR))

STATUS_LABELS = {
    "draft": "Черновик",
    "sealed": "Запечатан",
    "verified": "Верифицирован",
    "verified_with_discrepancy": "Расхождение",
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


# ─── Root ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    operator: str | None = Depends(_operator),
    is_admin: bool = Depends(get_is_admin),
):
    return templates.TemplateResponse(request, "index.html", {"operator": operator, "is_admin": is_admin})


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
    response = templates.TemplateResponse(
        request,
        "index.html",
        {"operator": name, "is_admin": op.is_admin and op.is_active},
    )
    response.set_cookie("operator_name", quote(name), httponly=True, samesite="lax")
    return response


@router.post("/ui/operator/clear", response_class=HTMLResponse)
async def clear_operator(request: Request):
    response = templates.TemplateResponse(request, "index.html", {"operator": None})
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
        envelope = await env_svc.get_by_id(session, envelope_id)
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
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')

    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        result = await verify_svc.finish(
            session, envelope=envelope, force=(force == "true"), operator=operator
        )
        await session.commit()
        envelope = await env_svc.get_by_id(session, envelope_id)
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
    is_admin: bool = Depends(get_is_admin),
):
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    printers = printer_svc.list_printers(get_settings())
    audit_ctx = await _audit_screen_context(session)
    return templates.TemplateResponse(
        request,
        "partials/admin_v2.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "operators": operators,
            "printers": printers,
            "show_reset": get_settings().env != "production",
            **audit_ctx,
        },
    )


async def _admin_v2_response(
    request: Request,
    session: AsyncSession,
    *,
    operator: str | None,
    is_admin: bool,
):
    operators = await op_svc.list_operators(session)
    printers = printer_svc.list_printers(get_settings())
    audit_ctx = await _audit_screen_context(session)
    return templates.TemplateResponse(
        request,
        "partials/admin_v2.html",
        {
            "operator": operator,
            "is_admin": is_admin,
            "operators": operators,
            "printers": printers,
            "show_reset": get_settings().env != "production",
            **audit_ctx,
        },
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
    )
    await session.commit()
    return await _admin_v2_response(request, session, operator=operator, is_admin=is_admin)


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
    for tbl in ("audit_log", "envelope_documents", "envelopes", "signers", "branches"):
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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))


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
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session, is_admin=is_admin))
