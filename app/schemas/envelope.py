import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import EnvelopeStatus
from app.schemas.document import DocumentOut


class EnvelopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    barcode: str
    status: EnvelopeStatus
    created_at: datetime
    sealed_at: datetime | None = None
    verified_at: datetime | None = None
    created_by: str
    verified_by: str | None = None
    origin_branch_id: uuid.UUID | None = None
    destination_branch_id: uuid.UUID | None = None
    signer_sender_id: uuid.UUID | None = None
    signer_receiver_id: uuid.UUID | None = None
    notes: str | None = None
    documents: list[DocumentOut] = []


class SealRequest(BaseModel):
    signer_sender_id: uuid.UUID
    signer_receiver_id: uuid.UUID
    origin_branch_id: uuid.UUID
    destination_branch_id: uuid.UUID
    notes: str | None = None
