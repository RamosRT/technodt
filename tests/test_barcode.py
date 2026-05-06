import re
import uuid

import pytest

from app.exceptions import BarcodeError
from app.services.barcode import doc_barcode_to_guid, generate_envelope_codes


def test_doc_barcode_to_guid_known_value():
    g = uuid.UUID("12345678-1234-5678-1234-567812345678")
    n = int.from_bytes(g.bytes, "big")
    assert doc_barcode_to_guid(str(n)) == g


def test_doc_barcode_to_guid_zero():
    assert doc_barcode_to_guid("0") == uuid.UUID(int=0)


def test_doc_barcode_to_guid_max_128_bit():
    n = (1 << 128) - 1
    assert doc_barcode_to_guid(str(n)).int == n


def test_doc_barcode_to_guid_too_large_raises():
    n = 1 << 128
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid(str(n))


def test_doc_barcode_to_guid_non_digit_raises():
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid("12abc")


def test_doc_barcode_to_guid_empty_raises():
    with pytest.raises(BarcodeError):
        doc_barcode_to_guid("")


def test_generate_envelope_codes_format():
    number, barcode = generate_envelope_codes()
    assert re.fullmatch(r"ТА-\d{16}", number)
    assert re.fullmatch(r"\d{16}", barcode)
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
