"""Print service: PDF (Playwright/Chromium) and ZPL label rendering."""
import asyncio
import base64
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


def generate_barcode_svg(
    barcode_value: str,
    *,
    module_width: float = 0.2,
    module_height: float = 10.0,
    quiet_zone: float = 2.0,
) -> str:
    """Return an embeddable SVG Code128 barcode (no XML declaration)."""
    import barcode as bc
    from barcode.writer import SVGWriter

    buf = io.BytesIO()
    bc.get_barcode_class("code128")(barcode_value, writer=SVGWriter()).write(
        buf,
        options={
            "write_text": False,
            "module_width": module_width,
            "module_height": module_height,
            "quiet_zone": quiet_zone,
        },
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
        # Screen/PDF scanners usually need thicker bars and more quiet zone.
        barcode_svg=generate_barcode_svg(
            envelope.barcode,
            module_width=0.5,
            module_height=16.0,
            quiet_zone=4.0,
        ),
        print_date=datetime.now(timezone.utc),
        **related,
    )
    html_str = _jinja_env().get_template("print/inventory.html").render(**ctx)
    return await _html_to_pdf(html_str)


async def render_label_pdf(session: AsyncSession, envelope_id: uuid.UUID) -> bytes:
    envelope = await get_by_id(session, envelope_id)

    ctx = dict(
        envelope=envelope,
        # Make label barcode wider/less dense for scanner readability on screen and print.
        barcode_svg=generate_barcode_svg(
            envelope.barcode,
            module_width=0.5,
            module_height=18.0,
            quiet_zone=1.0,
        ),
        print_date=datetime.now(timezone.utc),
    )
    html_str = _jinja_env().get_template("print/label.html").render(**ctx)
    return await _html_to_pdf(html_str)


async def render_label_zpl_for_envelope(
    session: AsyncSession, envelope_id: uuid.UUID, dpi: int = 200
) -> str:
    envelope = await get_by_id(session, envelope_id)
    return render_label_zpl(envelope, dpi=dpi)


async def render_discrepancy_act_pdf(session: AsyncSession, envelope_id: uuid.UUID) -> bytes:
    envelope = await get_by_id(session, envelope_id)
    related = await _load_related(session, envelope)

    # Missing documents first, then scanned ones.
    docs_sorted = sorted(
        list(envelope.documents),
        key=lambda d: (d.scanned_at_verification is not None, d.doc_date, d.doc_number),
    )

    ctx = dict(
        envelope=envelope,
        documents=docs_sorted,
        print_date=datetime.now(timezone.utc),
        **related,
    )
    html_str = _jinja_env().get_template("print/discrepancy_act.html").render(**ctx)
    return await _html_to_pdf(html_str)


def _render_qr_png_base64(payload: str) -> str:
    import qrcode

    qr = qrcode.QRCode(version=None, box_size=12, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def render_operator_auth_label_pdf(server_url: str, username: str, password: str) -> bytes:
    payload = f"KTLOGIN|{server_url.strip()}|{username}|{password}"
    qr_png_b64 = await asyncio.to_thread(_render_qr_png_base64, payload)
    html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <style>
    @page {{ size: 100mm 50mm; margin: 6mm; }}
    body {{
      font-family: Arial, sans-serif;
      margin: 0;
      color: #1b2848;
    }}
    .wrap {{
      display: grid;
      grid-template-columns: 36mm 1fr;
      gap: 6mm;
      align-items: center;
      height: 100%;
    }}
    img {{ width: 36mm; height: 36mm; }}
    .title {{ font-size: 14pt; font-weight: 700; margin-bottom: 2mm; }}
    .line {{ font-size: 10pt; margin: 0 0 1mm; }}
    .hint {{ font-size: 8.5pt; color: #4a5c7a; margin-top: 2mm; }}
  </style>
</head>
<body>
  <div class="wrap">
    <img src="data:image/png;base64,{qr_png_b64}" alt="QR auth" />
    <div>
      <div class="title">Вход ТСД</div>
      <p class="line"><strong>Оператор:</strong> {username}</p>
      <p class="line"><strong>PIN:</strong> {password}</p>
      <p class="hint">Отсканируйте QR на экране входа ТСД</p>
    </div>
  </div>
</body>
</html>"""
    return await _html_to_pdf(html)
