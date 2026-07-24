"""add discrepancy resolution fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "envelope_documents",
        sa.Column("discrepancy_resolved_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "envelope_documents",
        sa.Column("discrepancy_resolved_by", sa.String(200)),
    )
    op.create_index(
        "ix_envelope_documents_discrepancy_resolved_at",
        "envelope_documents",
        ["discrepancy_resolved_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_envelope_documents_discrepancy_resolved_at",
        table_name="envelope_documents",
    )
    op.drop_column("envelope_documents", "discrepancy_resolved_by")
    op.drop_column("envelope_documents", "discrepancy_resolved_at")
