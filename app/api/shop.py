"""Shopper-facing endpoints: catalog with filters and sorting, facets, deals and watches (alerts)."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from app import alerts
from app.api.dependencies import get_db
from app.api.routes import _apply_disclaimer, _like, _size_condition
from app.config import settings
from app.deals import find_deals
from app.models import Category, Product, ProductStatus, Watch
from app.search.fts import fts_available, match_all, ranked_matches
from app.security import watch_rate_limit

router = APIRouter()

WATCHER_RE = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
SORTS = ("relevance", "price_asc", "price_desc", "popular", "newest", "name")


def _cache() -> dict[str, str]:
    return {"Cache-Control": f"public, max-age={settings.cache_ttl_seconds}"}


@router.get("/api/catalog", tags=["shop"])
async def catalog(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    brand: str | None = Query(default=None, max_length=128),
    category_id: int | None = None,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    size: str | None = Query(default=None, max_length=8, pattern=r"^[A-Za-z0-9.,]+$"),
    in_stock: bool = True,
    sort: str = Query(default="relevance"),
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Browse the catalog like a shop: filter, sort and page (offset based)."""
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {', '.join(SORTS)}")
    statement = select(Product).where(Product.status != ProductStatus.DISAPPEARED)
    if in_stock:
        statement = statement.where(Product.available == True)  # noqa: E712
    if brand:
        statement = statement.where(Product.brand == brand)
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if min_price is not None:
        statement = statement.where(Product.price >= min_price)
    if max_price is not None:
        statement = statement.where(Product.price <= max_price)
    if size:
        statement = statement.where(_size_condition(size))

    rank = None
    if q:
        fts_query = match_all(q) if fts_available(db) else None
        if fts_query:
            fts = ranked_matches(fts_query, "fts_q")
            statement = statement.join(fts, fts.c.id == Product.id)
            rank = fts.c.rank
        else:
            statement = statement.where(Product.name.ilike(_like(q), escape="\\"))

    total = db.exec(select(func.count()).select_from(statement.subquery())).one()

    order = {
        "price_asc": [Product.price.asc()],
        "price_desc": [Product.price.desc()],
        "popular": [Product.view_count.desc()],
        "newest": [Product.created_at.desc()],
        "name": [Product.name.asc()],
        "relevance": ([rank] if rank is not None else []) + [Product.view_count.desc()],
    }[sort]
    products = db.exec(statement.order_by(*order, Product.id).offset(offset).limit(limit)).all()
    response.headers.update(_cache())
    return {
        "items": [_apply_disclaimer(p.model_dump()) for p in products],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _size_key(size: str) -> tuple[int, float, str]:
    try:
        return (0, float(size.replace(",", ".")), size)
    except ValueError:
        return (1, 0.0, size)  # P, M, G... after the numbers


@router.get("/api/facets", tags=["shop"])
async def facets(response: Response, db: Session = Depends(get_db)):
    """What the filters can offer: brands, sizes in stock, categories and the price range."""
    live = Product.status != ProductStatus.DISAPPEARED
    brands = db.exec(
        select(Product.brand, func.count()).where(live, Product.brand.is_not(None)).group_by(Product.brand)
    ).all()
    categories = db.exec(
        select(Category.id, Category.name, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .where(live)
        .group_by(Category.id)
    ).all()
    low, high = db.exec(select(func.min(Product.price), func.max(Product.price)).where(live)).one()
    sizes: Counter[str] = Counter()
    for product_sizes in db.exec(select(Product.sizes).where(live, Product.available == True)):  # noqa: E712
        sizes.update(set(product_sizes or []))
    response.headers.update(_cache())
    return {
        "brands": [{"brand": b, "count": c} for b, c in sorted(brands, key=lambda x: (-x[1], x[0]))],
        "sizes": [{"size": s, "count": sizes[s]} for s in sorted(sizes, key=_size_key)],
        "categories": [{"id": i, "name": n, "count": c} for i, n, c in sorted(categories, key=lambda x: -x[2])],
        "price": {"min": float(low) if low is not None else None, "max": float(high) if high is not None else None},
    }


@router.get("/api/deals", tags=["shop"])
async def deals(
    response: Response,
    days: int = Query(default=90, ge=7, le=365),
    min_discount: float = Query(default=5.0, ge=1, le=90),
    limit: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Products at their lowest recorded price of the last ``days`` days, biggest drop first."""
    found = find_deals(db, days=days, min_discount=min_discount, limit=limit)
    response.headers.update(_cache())
    return {
        "deals": [
            {
                "discount_pct": d["discount_pct"],
                "was": float(d["was"]),
                "now": float(d["now"]),
                "days": d["days"],
                "product": _apply_disclaimer(d["product"].model_dump()),
            }
            for d in found
        ]
    }


# ---------------------------------------------------------------------------
# Watches (alerts). No accounts: X-Watcher-Id is a random secret kept by the browser.
# ---------------------------------------------------------------------------


def _watcher(x_watcher_id: str | None = Header(default=None)) -> str:
    if not x_watcher_id or not WATCHER_RE.match(x_watcher_id):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Watcher-Id")
    return x_watcher_id


class WatchCreate(BaseModel):
    product_id: int
    size: str | None = Field(default=None, max_length=32)
    target_price: Decimal | None = Field(default=None, gt=0, lt=1_000_000)
    channel: str = Field(max_length=16)
    destination: str = Field(min_length=1, max_length=512)


def _view(w: Watch) -> dict:
    return {
        "id": w.id,
        "product_id": w.product_id,
        "size": w.size,
        "target_price": float(w.target_price) if w.target_price is not None else None,
        "channel": w.channel,
        "destination": alerts.mask_destination(w.channel, w.destination),
        "created_at": w.created_at.isoformat(),
        "last_notified_at": w.last_notified_at.isoformat() if w.last_notified_at else None,
    }


@router.get("/api/alerts/config", tags=["alerts"])
async def alerts_config():
    """Which alert channels this server offers (empty when ALERTS_ENABLED is off)."""
    return {"enabled": settings.alerts_enabled, "channels": alerts.available_channels()}


@router.post("/api/watches", tags=["alerts"], dependencies=[Depends(watch_rate_limit)], status_code=201)
async def create_watch(payload: WatchCreate, watcher: str = Depends(_watcher), db: Session = Depends(get_db)):
    """Watch a product (optionally one size, optionally a target price) and get notified."""
    if not settings.alerts_enabled:
        raise HTTPException(status_code=503, detail="Alerts are disabled on this server")
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        destination = alerts.normalize_destination(payload.channel, payload.destination)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    mine = db.exec(select(Watch).where(Watch.watcher_id == watcher)).all()
    existing = next((w for w in mine if w.product_id == product.id and w.size == payload.size), None)
    if existing is None and len(mine) >= settings.alerts_max_watches_per_watcher:
        raise HTTPException(status_code=409, detail="Too many watches; remove one first")
    watch = existing or Watch(watcher_id=watcher, product_id=product.id, size=payload.size, channel="", destination="")
    watch.channel, watch.destination, watch.target_price = payload.channel, destination, payload.target_price
    watch.baseline_price = product.price
    watch.last_available = alerts._buyable(product, payload.size)
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return _view(watch)


@router.get("/api/watches", tags=["alerts"])
async def list_watches(watcher: str = Depends(_watcher), db: Session = Depends(get_db)):
    rows = db.exec(select(Watch).where(Watch.watcher_id == watcher).order_by(Watch.id)).all()
    return {"watches": [_view(w) for w in rows]}


@router.delete("/api/watches/{watch_id}", tags=["alerts"], status_code=204)
async def delete_watch(watch_id: int, watcher: str = Depends(_watcher), db: Session = Depends(get_db)):
    watch = db.exec(select(Watch).where(Watch.id == watch_id, Watch.watcher_id == watcher)).first()
    if watch is None:
        raise HTTPException(status_code=404, detail="Watch not found")
    db.delete(watch)
    db.commit()
