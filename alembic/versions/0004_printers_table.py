"""printers table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-06
"""

import json
import os

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


printers = sa.table(
    "printers",
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("kind", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("host", sa.String),
    sa.column("port", sa.Integer),
    sa.column("dpi", sa.Integer),
    sa.column("share_name", sa.String),
)


def upgrade() -> None:
    op.create_table(
        "printers",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("dpi", sa.Integer(), nullable=True),
        sa.Column("share_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('zpl', 'a4')", name="ck_printers_kind"),
    )
    raw = os.getenv("PRINTERS_JSON", "[]")
    try:
        seed = json.loads(raw)
    except json.JSONDecodeError:
        seed = []
    if isinstance(seed, list) and seed:
        rows = []
        for item in seed:
            if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
                continue
            rows.append(
                {
                    "id": str(item["id"]),
                    "name": str(item["name"]),
                    "kind": str(item.get("kind") or "zpl"),
                    "is_active": bool(item.get("is_active", True)),
                    "host": item.get("host"),
                    "port": item.get("port"),
                    "dpi": item.get("dpi"),
                    "share_name": item.get("share_name"),
                }
            )
        if rows:
            op.bulk_insert(printers, rows)


def downgrade() -> None:
    op.drop_table("printers")
