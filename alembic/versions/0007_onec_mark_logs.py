"""1C mark logs

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onec_mark_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("envelope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("doc_guid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_entity", sa.String(length=100), nullable=False),
        sa.Column("property_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["envelope_id"], ["envelopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onec_mark_logs_attempted_at", "onec_mark_logs", ["attempted_at"], unique=False)
    op.create_index("ix_onec_mark_logs_doc_guid", "onec_mark_logs", ["doc_guid"], unique=False)
    op.create_index("ix_onec_mark_logs_envelope_id", "onec_mark_logs", ["envelope_id"], unique=False)
    op.create_index("ix_onec_mark_logs_status", "onec_mark_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_onec_mark_logs_status", table_name="onec_mark_logs")
    op.drop_index("ix_onec_mark_logs_envelope_id", table_name="onec_mark_logs")
    op.drop_index("ix_onec_mark_logs_doc_guid", table_name="onec_mark_logs")
    op.drop_index("ix_onec_mark_logs_attempted_at", table_name="onec_mark_logs")
    op.drop_table("onec_mark_logs")
