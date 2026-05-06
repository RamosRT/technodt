"""Unit tests for app.services.printing — ZPL rendering and barcode SVG."""
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.services.printing import generate_barcode_svg, render_label_zpl


# Override the autouse DB fixture — these are pure unit tests with no DB dependency.
@pytest_asyncio.fixture(autouse=True)
async def truncate_tables():
    yield


def _env(barcode="1234567890123456", number="ТА-1234567890123456"):
    return SimpleNamespace(barcode=barcode, number=number)


# ── ZPL rendering (pure Jinja2, no external deps) ────────────────────────────


def test_render_label_zpl_200dpi_contains_zpl_start_and_end():
    zpl = render_label_zpl(_env(), dpi=200)
    assert "^XA" in zpl
    assert "^XZ" in zpl


def test_render_label_zpl_200dpi_sets_correct_label_dimensions():
    zpl = render_label_zpl(_env(), dpi=200)
    assert "^PW787" in zpl
    assert "^LL394" in zpl


def test_render_label_zpl_300dpi_sets_correct_label_dimensions():
    zpl = render_label_zpl(_env(), dpi=300)
    assert "^PW1181" in zpl
    assert "^LL591" in zpl


def test_render_label_zpl_embeds_barcode_value():
    env = _env(barcode="9876543210987654")
    zpl = render_label_zpl(env, dpi=200)
    assert "9876543210987654" in zpl


def test_render_label_zpl_embeds_envelope_number():
    env = _env(number="ТА-9876543210987654")
    zpl = render_label_zpl(env, dpi=200)
    assert "ТА-9876543210987654" in zpl


def test_render_label_zpl_unsupported_dpi_raises():
    with pytest.raises(Exception):
        render_label_zpl(_env(), dpi=150)


# ── Barcode SVG generation ────────────────────────────────────────────────────


def test_generate_barcode_svg_returns_svg_element():
    """Real call to python-barcode; result must be an embeddable SVG fragment."""
    svg = generate_barcode_svg("1234567890123456")
    assert svg.strip().startswith("<svg")
    assert "</svg>" in svg


def test_generate_barcode_svg_does_not_include_xml_declaration():
    svg = generate_barcode_svg("1234567890123456")
    assert "<?xml" not in svg
