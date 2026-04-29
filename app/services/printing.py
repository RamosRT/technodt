"""Print service: PDF (Playwright/Chromium) and ZPL label rendering."""
import asyncio
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.signer import Signer
from app.services.envelopes import get_by_id

_TEMPLATES = Path(__file__).parent.parent / "web" / "templates"
_SUPPORTED_ZPL_DPI = {200, 300}


def _jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(_TEMPLATES)), autoescape=False)


# ── thin wrappers (mocked in tests) ──────────────────────────────────────────


def _render_pdf_sync(html_str: str) -> bytes:
    """Render HTML to PDF via playwright sync API.

    Must run in a thread (via asyncio.to_thread) because sync_playwright
    manages its own subprocess/thread internally and is immune to whatever
    event loop policy uvicorn sets on Windows.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html_str, wait_until="networkidle")
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        browser.close()
        return pdf


async def _html_to_pdf(html_str: str) -> bytes:
    return await asyncio.to_thread(_render_pdf_sync, html_str)


def generate_barcode_svg(barcode_value: str) -> str:
    """Return an embeddable SVG Code128 barcode (no XML declaration)."""
    import barcode as bc
    from barcode.writer import SVGWriter

    buf = io.BytesIO()
    bc.get_barcode_class("code128")(barcode_value, writer=SVGWriter()).write(
        buf, options={"write_text": False, "module_height": 10.0}
    )
    raw = buf.getvalue().decode("utf-8")
    # Strip XML declaration so it can be embedded inline
    return raw[raw.index("<svg"):]


# ── ZPL ──────────────────────────────────────────────────────────────────────


def render_label_zpl(envelope, dpi: int = 200) -> str:
    """Render ZPL II label template for the given envelope."""
    if dpi not in _SUPPORTED_ZPL_DPI:
        raise ValueError(f"Unsupported DPI {dpi}; supported: {sorted(_SUPPORTED_ZPL_DPI)}")
    tmpl = _jinja_env().get_template(f"print/label_{dpi}dpi.zpl.j2")
    return tmpl.render(envelope=envelope)


# ── helpers ───────────────────────────────────────────────────────────────────


async def _load_related(session: AsyncSession, envelope) -> dict:
    """Fetch Branch/Signer objects referenced by the envelope."""
    ids_branches = {
        k: v for k, v in [
            ("origin_branch", envelope.origin_branch_id),
            ("destination_branch", envelope.destination_branch_id),
        ] if v is not None
    }
    ids_signers = {
        k: v for k, v in [
            ("signer_sender", envelope.signer_sender_id),
            ("signer_receiver", envelope.signer_receiver_id),
        ] if v is not None
    }

    branches: dict[str, Branch] = {}
    if ids_branches:
        rows = (await session.execute(
            select(Branch).where(Branch.id.in_(ids_branches.values()))
        )).scalars().all()
        by_id = {b.id: b for b in rows}
        branches = {k: by_id[v] for k, v in ids_branches.items() if v in by_id}

    signers: dict[str, Signer] = {}
    if ids_signers:
        rows = (await session.execute(
            select(Signer).where(Signer.id.in_(ids_signers.values()))
        )).scalars().all()
        by_id = {s.id: s for s in rows}
        signers = {k: by_id[v] for k, v in ids_signers.items() if v in by_id}

    return {
        "origin_branch": branches.get("origin_branch"),
        "destination_branch": branches.get("destination_branch"),
        "signer_sender": signers.get("signer_sender"),
        "signer_receiver": signers.get("signer_receiver"),
    }


# ── public async API ─────────────────────────────────────────────────────────


async def render_inventory_pdf(session: AsyncSession, envelope_id: uuid.UUID) -> bytes:
    envelope = await get_by_id(session, envelope_id)
    related = await _load_related(session, envelope)

    ctx = dict(
        envelope=envelope,
        documents=list(envelope.documents),
        barcode_svg=generate_barcode_svg(envelope.barcode),
        print_date=datetime.now(timezone.utc),
        **related,
    )
    html_str = _jinja_env().get_template("print/inventory.html").render(**ctx)
    return await _html_to_pdf(html_str)


async def render_label_pdf(session: AsyncSession, envelope_id: uuid.UUID) -> bytes:
    envelope = await get_by_id(session, envelope_id)

    ctx = dict(
        envelope=envelope,
        barcode_svg=generate_barcode_svg(envelope.barcode),
        print_date=datetime.now(timezone.utc),
    )
    html_str = _jinja_env().get_template("print/label.html").render(**ctx)
    return await _html_to_pdf(html_str)


async def render_label_zpl_for_envelope(
    session: AsyncSession, envelope_id: uuid.UUID, dpi: int = 200
) -> str:
    envelope = await get_by_id(session, envelope_id)
    return render_label_zpl(envelope, dpi=dpi)
