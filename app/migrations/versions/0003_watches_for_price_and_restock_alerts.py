"""watches for price and restock alerts

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22 22:24:27.734962
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watcher_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("size", sa.String(length=32), nullable=True),
        sa.Column("target_price", sa.Numeric(), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("destination", sa.String(length=512), nullable=False),
        sa.Column("baseline_price", sa.Numeric(), nullable=True),
        sa.Column("last_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("watches", schema=None) as batch_op:
        batch_op.create_index("ix_watches_product_id", ["product_id"], unique=False)
        batch_op.create_index("ix_watches_watcher_id", ["watcher_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("watches", schema=None) as batch_op:
        batch_op.drop_index("ix_watches_watcher_id")
        batch_op.drop_index("ix_watches_product_id")

    op.drop_table("watches")
