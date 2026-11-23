from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import JSON, Column, Field, Index, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProductStatus(str, Enum):
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    DISAPPEARED = "disappeared"


class Installments(SQLModel):
    count: int
    value: Decimal
    interest_free: bool


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int = Field(primary_key=True)
    slug: str = Field(max_length=255)
    url: str = Field(max_length=1024)
    name: str | None = Field(default=None, max_length=255)
    product_count: int = Field(default=0)
    last_seen: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_brand", "brand"),
        Index("ix_products_status", "status"),
        Index("ix_products_view_count", "view_count"),
    )

    id: int = Field(primary_key=True)
    slug: str = Field(max_length=255)
    url: str = Field(max_length=1024)
    name: str = Field(max_length=512)
    codigo: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="BRL", max_length=8)
    price: Decimal | None = Field(default=None)
    price_boleto: Decimal | None = Field(default=None)
    installments: dict | None = Field(default=None, sa_column=Column(JSON(none_as_null=True)))
    sizes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    available: bool = Field(default=False)
    description: str | None = Field(default=None)
    images: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    breadcrumbs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    brand: str | None = Field(default=None, max_length=128)
    status: ProductStatus = Field(default=ProductStatus.ACTIVE)
    scraped_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    view_count: int = Field(default=0)
    # Consecutive full crawls whose listings did not contain this product (disappearance detection).
    missing_crawls: int = Field(default=0)


class ProductHistory(SQLModel, table=True):
    __tablename__ = "product_history"
    __table_args__ = (Index("ix_product_history_scraped_at", "product_id", "scraped_at"),)

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    price: Decimal | None = Field(default=None)
    price_boleto: Decimal | None = Field(default=None)
    available: bool = Field(default=False)
    status: ProductStatus = Field(default=ProductStatus.ACTIVE)
    scraped_at: datetime = Field(default_factory=utcnow)


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"
    __table_args__ = (Index("ix_scrape_runs_started_at", "started_at"),)

    id: int | None = Field(default=None, primary_key=True)
    run_type: str = Field(max_length=32)  # "full" | "incremental" | "single"
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = Field(default=None)
    products_scraped: int = Field(default=0)
    products_failed: int = Field(default=0)
    products_disappeared: int = Field(default=0)
    status: str = Field(default="running", max_length=32)  # running | completed | failed
    error_message: str | None = Field(default=None)


class ParseFailure(SQLModel, table=True):
    """The latest pages that failed to parse, with a sample of the HTML for debugging."""

    __tablename__ = "parse_failures"
    __table_args__ = (Index("ix_parse_failures_created_at", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(max_length=1024)
    error: str = Field(max_length=1024)
    http_status: int | None = Field(default=None)
    html_sample: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class Watch(SQLModel, table=True):
    """A shopper's alert: price drops and restocks of one product, delivered to ntfy or a webhook.

    There are no accounts: ``watcher_id`` is a random secret the browser keeps and sends as a
    header, and it is the only key to its watches. ``destination`` is an ntfy topic or a webhook
    URL the shopper chose; it is never returned in full by the API.
    """

    __tablename__ = "watches"
    __table_args__ = (Index("ix_watches_watcher_id", "watcher_id"), Index("ix_watches_product_id", "product_id"))

    id: int | None = Field(default=None, primary_key=True)
    watcher_id: str = Field(max_length=64)
    product_id: int = Field(foreign_key="products.id")
    size: str | None = Field(default=None, max_length=32)
    target_price: Decimal | None = Field(default=None)
    channel: str = Field(max_length=16)  # "ntfy" | "webhook"
    destination: str = Field(max_length=512)
    # State, updated on every evaluation: the price to beat and whether the product/size was buyable.
    baseline_price: Decimal | None = Field(default=None)
    last_available: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    last_notified_at: datetime | None = Field(default=None)
