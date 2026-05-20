"""add onec_documents table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onec_documents",
        sa.Column("guid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("print_number", sa.String(100), nullable=False),
        sa.Column("doc_date", sa.Date, nullable=False),
        sa.Column("is_correction", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("partner_name", sa.String(500)),
        sa.Column("is_edo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("related_realization_number", sa.String(50)),
        sa.Column("kzv_copy_link", sa.Text),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("first_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("archive_processed_at", sa.DateTime(timezone=True)),
        sa.Column("archive_storage_path", sa.Text),
        sa.Column("archive_download_url", sa.Text),
    )
    op.create_index("ix_onec_documents_doc_date", "onec_documents", ["doc_date"])
    op.create_index("ix_onec_documents_is_deleted", "onec_documents", ["is_deleted"])
    op.create_index("ix_onec_documents_print_number", "onec_documents", ["print_number"])


def downgrade() -> None:
    op.drop_index("ix_onec_documents_print_number", table_name="onec_documents")
    op.drop_index("ix_onec_documents_is_deleted", table_name="onec_documents")
    op.drop_index("ix_onec_documents_doc_date", table_name="onec_documents")
    op.drop_table("onec_documents")
