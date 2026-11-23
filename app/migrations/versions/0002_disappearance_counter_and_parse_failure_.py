"""disappearance counter and parse failure samples

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22 22:12:45.208511
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parse_failures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("error", sa.String(length=1024), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("html_sample", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("parse_failures", schema=None) as batch_op:
        batch_op.create_index("ix_parse_failures_created_at", ["created_at"], unique=False)

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("missing_crawls", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("missing_crawls")

    with op.batch_alter_table("parse_failures", schema=None) as batch_op:
        batch_op.drop_index("ix_parse_failures_created_at")

    op.drop_table("parse_failures")
