"""operator passwords and printer assignment

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operators", sa.Column("password_hash", sa.String(260), nullable=True))
    op.add_column("operators", sa.Column("assigned_zpl_printer_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("operators", "assigned_zpl_printer_id")
    op.drop_column("operators", "password_hash")
