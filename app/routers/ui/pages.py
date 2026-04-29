"""UI routes — renders Jinja2 templates for the single-page HTMX frontend."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_one_c_client
from app.exceptions import AppError
import app.services.envelopes as env_svc
import app.services.dictionaries as dict_svc
import app.services.verify as verify_svc
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


def _operator(operator_name: str | None = Cookie(default=None)) -> str | None:
    return operator_name or None


# ─── Root ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, operator: str | None = Depends(_operator)):
    return templates.TemplateResponse(request, "index.html", {"operator": operator})


# ─── Operator ────────────────────────────────────────────────────────────────

@router.post("/ui/operator", response_class=HTMLResponse)
async def set_operator(request: Request, operator_name: str = Form(...)):
    response = templates.TemplateResponse(request, "index.html", {"operator": operator_name})
    response.set_cookie("operator_name", operator_name, httponly=True, samesite="lax")
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
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')

    envelope = await env_svc.create_envelope(session, operator=operator)
    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)

    return templates.TemplateResponse(request, "partials/envelope_card.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "branches": branches,
        "signers": signers,
        "status_labels": STATUS_LABELS,
    })


# ─── Add document ─────────────────────────────────────────────────────────────

@router.post("/ui/envelopes/{envelope_id}/documents", response_class=HTMLResponse)
async def ui_add_document(
    request: Request,
    envelope_id: uuid.UUID,
    barcode: str = Form(...),
    session: AsyncSession = Depends(get_session),
    one_c: OneCClient = Depends(get_one_c_client),
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.add_document(session, envelope=envelope, barcode=barcode, one_c=one_c, operator=operator)
        await session.refresh(envelope)
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(request, "partials/doc_table.html", {
        "envelope": envelope,
        "documents": envelope.documents,
    })


# ─── Remove document ──────────────────────────────────────────────────────────

@router.delete("/ui/envelopes/{envelope_id}/documents/{doc_id}", response_class=HTMLResponse)
async def ui_remove_document(
    request: Request,
    envelope_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    if not operator:
        return HTMLResponse('<div class="alert alert-error">Требуется войти в систему</div>')
    try:
        envelope = await env_svc.get_by_id(session, envelope_id)
        await env_svc.remove_document(session, envelope=envelope, doc_id=doc_id, operator=operator)
        await session.refresh(envelope)
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    return templates.TemplateResponse(request, "partials/doc_table.html", {
        "envelope": envelope,
        "documents": envelope.documents,
    })


# ─── Seal ─────────────────────────────────────────────────────────────────────

@router.post("/ui/envelopes/{envelope_id}/seal", response_class=HTMLResponse)
async def ui_seal_envelope(
    request: Request,
    envelope_id: uuid.UUID,
    signer_sender_id: uuid.UUID = Form(...),
    signer_receiver_id: uuid.UUID = Form(...),
    origin_branch_id: uuid.UUID = Form(...),
    destination_branch_id: uuid.UUID = Form(...),
    notes: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
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
        await session.refresh(envelope)
    except AppError as e:
        return HTMLResponse(f'<div class="alert alert-error">{e.detail}</div>', status_code=e.status_code)

    branches = await dict_svc.list_branches(session, only_active=True)
    signers = await dict_svc.list_signers(session, only_active=True)

    return templates.TemplateResponse(request, "partials/envelope_card.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "branches": branches,
        "signers": signers,
        "status_labels": STATUS_LABELS,
    })


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
        await verify_svc.start(session, envelope=envelope, operator=operator)
        await session.refresh(envelope)
    except AppError as e:
        return templates.TemplateResponse(request, "partials/verify_prompt.html", {"error": e.detail})

    scanned = sum(1 for d in envelope.documents if d.scanned_at_verification)
    return templates.TemplateResponse(request, "partials/verify_card.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "scanned_count": scanned,
        "all_scanned": scanned == len(envelope.documents),
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
    await session.refresh(envelope)

    just_scanned_id = result.doc_id if result.matched else None
    for doc in envelope.documents:
        doc.just_scanned = (doc.id == just_scanned_id)

    scanned = sum(1 for d in envelope.documents if d.scanned_at_verification)
    return templates.TemplateResponse(request, "partials/verify_table.html", {
        "documents": envelope.documents,
        "scanned_count": scanned,
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

    envelope = await env_svc.get_by_id(session, envelope_id)
    result = await verify_svc.finish(
        session, envelope=envelope, force=(force == "true"), operator=operator
    )
    await session.refresh(envelope)

    return templates.TemplateResponse(request, "partials/verify_done.html", {
        "envelope": envelope,
        "documents": envelope.documents,
        "missing_count": len(result.missing_doc_ids),
    })


# ─── Admin / dictionaries ─────────────────────────────────────────────────────

async def _admin_ctx(session: AsyncSession) -> dict:
    return {
        "branches": await dict_svc.list_branches(session, only_active=False),
        "signers": await dict_svc.list_signers(session, only_active=False),
    }


@router.get("/ui/admin", response_class=HTMLResponse)
async def ui_admin(request: Request, session: AsyncSession = Depends(get_session)):
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session))


@router.post("/ui/admin/branches", response_class=HTMLResponse)
async def ui_create_branch(
    request: Request,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    await dict_svc.create_branch(session, name=name, operator=operator or "ui")
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session))


@router.patch("/ui/admin/branches/{branch_id}", response_class=HTMLResponse)
async def ui_patch_branch(
    request: Request,
    branch_id: uuid.UUID,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    await dict_svc.patch_branch(session, branch_id=branch_id, name=name, is_active=None, operator=operator or "ui")
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session))


@router.post("/ui/admin/signers", response_class=HTMLResponse)
async def ui_create_signer(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    await dict_svc.create_signer(
        session, last_name=last_name, first_name=first_name, operator=operator or "ui"
    )
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session))


@router.patch("/ui/admin/signers/{signer_id}", response_class=HTMLResponse)
async def ui_patch_signer(
    request: Request,
    signer_id: uuid.UUID,
    last_name: str = Form(...),
    first_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
    operator: str | None = Depends(_operator),
):
    await dict_svc.patch_signer(
        session, signer_id=signer_id, last_name=last_name, first_name=first_name,
        is_active=None, operator=operator or "ui"
    )
    return templates.TemplateResponse(request, "partials/admin.html", await _admin_ctx(session))
