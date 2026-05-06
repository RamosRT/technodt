import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_barcode: str
    doc_guid: uuid.UUID
    doc_entity: str
    doc_kind: str
    doc_number: str
    doc_date: date
    related_realization_number: str | None = None
    related_realization_date: date | None = None
    added_at: datetime
    scanned_at_verification: datetime | None = None

    @field_validator("doc_kind", mode="before")
    @classmethod
    def normalize_transfer_kind(cls, value: str) -> str:
        if value == "Перемещение товаров":
            return "ПРМ"
        return value


class DocumentAddRequest(BaseModel):
    barcode: str
