import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class ReportDocumentRow(BaseModel):
    guid: uuid.UUID
    number: str
    doc_date: date
    doc_type: str
    partner_name: Optional[str] = None
    is_edo: bool
    related_realization_number: Optional[str] = None
    registered_at: Optional[datetime] = None
    sealed_at: Optional[datetime] = None
    envelope_number: Optional[str] = None
    origin_branch: Optional[str] = None
    created_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    destination_branch: Optional[str] = None
    has_discrepancy: bool = False
    mark_registered_at: Optional[datetime] = None
    mark_sealed_at: Optional[datetime] = None
    mark_verified_at: Optional[datetime] = None
    archive_processed_at: Optional[datetime] = None
    archive_storage_path: Optional[str] = None
    archive_download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    items: list[ReportDocumentRow]
    total: int
    page: int
    page_size: int
