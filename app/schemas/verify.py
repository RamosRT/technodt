import uuid
from datetime import datetime

from pydantic import BaseModel


class VerifyScanRequest(BaseModel):
    barcode: str


class VerifyScanResponse(BaseModel):
    matched: bool
    doc_id: uuid.UUID | None = None
    scanned_at: datetime | None = None
    reason: str | None = None


class VerifyFinishRequest(BaseModel):
    force: bool = False


class VerifyFinishResponse(BaseModel):
    status: str
    missing_docs: list[uuid.UUID] = []
