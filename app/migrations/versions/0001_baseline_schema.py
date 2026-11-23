"""baseline schema (the schema of version 0.4.0)

Existing installations already have these tables: app.db stamps them at this revision
instead of running it (see run_migrations).

Revision ID: 0001
Revises:
Create Date: 2026-11-22 22:11:50.530079
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("products_scraped", sa.Integer(), nullable=False),
        sa.Column("products_failed", sa.Integer(), nullable=False),
        sa.Column("products_disappeared", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scrape_runs", schema=None) as batch_op:
        batch_op.create_index("ix_scrape_runs_started_at", ["started_at"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("price_boleto", sa.Numeric(), nullable=True),
        sa.Column("installments", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("sizes", sa.JSON(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("breadcrumbs", sa.JSON(), nullable=True),
        sa.Column("brand", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "OUT_OF_STOCK", "DISAPPEARED", name="productstatus"), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.create_index("ix_products_brand", ["brand"], unique=False)
        batch_op.create_index("ix_products_category_id", ["category_id"], unique=False)
        batch_op.create_index("ix_products_status", ["status"], unique=False)
        batch_op.create_index("ix_products_view_count", ["view_count"], unique=False)

    op.create_table(
        "product_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("price_boleto", sa.Numeric(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "OUT_OF_STOCK", "DISAPPEARED", name="productstatus"), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("product_history", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_product_history_product_id"), ["product_id"], unique=False)
        batch_op.create_index("ix_product_history_scraped_at", ["product_id", "scraped_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("product_history", schema=None) as batch_op:
        batch_op.drop_index("ix_product_history_scraped_at")
        batch_op.drop_index(batch_op.f("ix_product_history_product_id"))

    op.drop_table("product_history")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index("ix_products_view_count")
        batch_op.drop_index("ix_products_status")
        batch_op.drop_index("ix_products_category_id")
        batch_op.drop_index("ix_products_brand")

    op.drop_table("products")
    with op.batch_alter_table("scrape_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_scrape_runs_started_at")

    op.drop_table("scrape_runs")
    op.drop_table("categories")
