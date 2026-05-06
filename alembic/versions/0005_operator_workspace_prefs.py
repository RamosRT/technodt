"""operator workspace preferences

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operators", sa.Column("assigned_a4_printer_id", sa.String(length=100), nullable=True))
    op.add_column("operators", sa.Column("default_branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("operators", sa.Column("default_signer_sender_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("operators", "default_signer_sender_id")
    op.drop_column("operators", "default_branch_id")
    op.drop_column("operators", "assigned_a4_printer_id")
