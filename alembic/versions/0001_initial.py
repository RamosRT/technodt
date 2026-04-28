"""initial

Revision ID: 0001
Revises:
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "signers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "envelopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("barcode", sa.String(40), nullable=False, unique=True),
        sa.Column("status", postgresql.ENUM("draft", "sealed", "verified", "verified_with_discrepancy", name="envelope_status"), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sealed_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("verified_by", sa.String(200)),
        sa.Column("origin_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("destination_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("signer_sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signers.id")),
        sa.Column("signer_receiver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signers.id")),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_envelopes_barcode", "envelopes", ["barcode"], unique=True)
    op.create_table(
        "envelope_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("envelopes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_barcode", sa.String(64), nullable=False),
        sa.Column("doc_guid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_entity", sa.String(100), nullable=False),
        sa.Column("doc_kind", sa.String(50), nullable=False),
        sa.Column("doc_number", sa.String(50), nullable=False),
        sa.Column("doc_date", sa.Date, nullable=False),
        sa.Column("related_realization_number", sa.String(50)),
        sa.Column("related_realization_date", sa.Date),
        sa.Column("raw_1c_payload", postgresql.JSONB, nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("scanned_at_verification", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("envelope_id", "doc_guid", name="uq_envelope_doc_guid"),
    )
    op.create_index("ix_envelope_documents_envelope_id", "envelope_documents", ["envelope_id"])
    op.create_index("ix_envelope_documents_doc_barcode", "envelope_documents", ["doc_barcode"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("envelopes.id", ondelete="SET NULL")),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("actor", sa.String(200), nullable=False, server_default="system"),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_envelope_id", "audit_log", ["envelope_id"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("envelope_documents")
    op.drop_table("envelopes")
    op.drop_table("signers")
    op.drop_table("branches")
    op.execute("DROP TYPE envelope_status")
