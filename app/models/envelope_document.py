import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .envelope import Envelope


class EnvelopeDocument(Base):
    __tablename__ = "envelope_documents"
    __table_args__ = (UniqueConstraint("envelope_id", "doc_guid", name="uq_envelope_doc_guid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("envelopes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    doc_barcode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    doc_entity: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_date: Mapped[date] = mapped_column(Date, nullable=False)
    related_realization_number: Mapped[str | None] = mapped_column(String(50))
    related_realization_date: Mapped[date | None] = mapped_column(Date)
    raw_1c_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scanned_at_verification: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    envelope: Mapped["Envelope"] = relationship(back_populates="documents")
