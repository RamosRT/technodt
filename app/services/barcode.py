import secrets
import uuid

from app.config import get_settings
from app.exceptions import BarcodeError


def doc_barcode_to_guid(barcode: str) -> uuid.UUID:
    if not barcode or not barcode.isdigit():
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    n = int(barcode)
    if n.bit_length() > 128:
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    return uuid.UUID(bytes=n.to_bytes(16, "big"))


def generate_envelope_codes() -> tuple[str, str]:
    """Returns (number, barcode). number = 'ТА-' + barcode. barcode is 16 digits."""
    prefix = get_settings().envelope_bc_prefix
    digits_needed = 16 - len(prefix)
    if digits_needed <= 0:
        raise ValueError("ENVELOPE_BC_PREFIX must be shorter than 16 chars")
    tail = "".join(secrets.choice("0123456789") for _ in range(digits_needed))
    barcode = prefix + tail
    return f"ТА-{barcode}", barcode
