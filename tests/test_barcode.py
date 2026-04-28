import uuid
import pytest

from app.exceptions import BarcodeError
from app.services.barcode import doc_barcode_to_guid


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
