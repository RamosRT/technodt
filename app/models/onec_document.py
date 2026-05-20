import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OneCDocument(Base):
    __tablename__ = "onec_documents"

    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    print_number: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    partner_name: Mapped[str | None] = mapped_column(String(500))
    is_edo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    related_realization_number: Mapped[str | None] = mapped_column(String(50))
    kzv_copy_link: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    first_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archive_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_storage_path: Mapped[str | None] = mapped_column(Text)
    archive_download_url: Mapped[str | None] = mapped_column(Text)
