import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .envelope_document import EnvelopeDocument


class EnvelopeStatus(enum.Enum):
    draft = "draft"
    sealed = "sealed"
    verified = "verified"
    verified_with_discrepancy = "verified_with_discrepancy"


class Envelope(Base):
    __tablename__ = "envelopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    barcode: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    status: Mapped[EnvelopeStatus] = mapped_column(
        Enum(EnvelopeStatus, name="envelope_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=EnvelopeStatus.draft,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(200))
    origin_branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    destination_branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    signer_sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signers.id"))
    signer_receiver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signers.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["EnvelopeDocument"]] = relationship(
        back_populates="envelope", cascade="all, delete-orphan", lazy="selectin"
    )
