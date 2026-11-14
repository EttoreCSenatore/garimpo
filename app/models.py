from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel


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

    id: int = Field(primary_key=True)
    slug: str = Field(max_length=255)
    url: str = Field(max_length=1024)
    name: str = Field(max_length=512)
    codigo: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="BRL", max_length=8)
    price: Decimal | None = Field(default=None)
    price_boleto: Decimal | None = Field(default=None)
    installments: dict | None = Field(default=None, sa_column=Column(JSON))
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


class ProductHistory(SQLModel, table=True):
    __tablename__ = "product_history"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    price: Decimal | None = Field(default=None)
    price_boleto: Decimal | None = Field(default=None)
    available: bool = Field(default=False)
    status: ProductStatus = Field(default=ProductStatus.ACTIVE)
    scraped_at: datetime = Field(default_factory=utcnow)


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"

    id: int | None = Field(default=None, primary_key=True)
    run_type: str = Field(max_length=32)  # "full" | "incremental" | "single"
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = Field(default=None)
    products_scraped: int = Field(default=0)
    products_failed: int = Field(default=0)
    products_disappeared: int = Field(default=0)
    status: str = Field(default="running", max_length=32)  # running | completed | failed
    error_message: str | None = Field(default=None)
