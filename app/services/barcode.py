import uuid

from app.exceptions import BarcodeError


def doc_barcode_to_guid(barcode: str) -> uuid.UUID:
    if not barcode or not barcode.isdigit():
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    n = int(barcode)
    if n.bit_length() > 128:
        raise BarcodeError("ШК не похож на штрихкод документа 1С")
    return uuid.UUID(bytes=n.to_bytes(16, "big"))
