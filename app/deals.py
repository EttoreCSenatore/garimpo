"""Deals: products priced at the lowest point of their own recorded history.

"On sale" claims by a store are not trusted: a deal here is a real price drop that Garimpo
recorded, compared with the highest price it saw for the same product in the window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.models import Product, ProductHistory, ProductStatus


def find_deals(db: Session, *, days: int = 90, min_discount: float = 5.0, limit: int = 24) -> list[dict]:
    """Available products whose current price is their lowest in ``days`` and clearly below the high."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.exec(
        select(ProductHistory.product_id, ProductHistory.price, ProductHistory.scraped_at)
        .where(ProductHistory.scraped_at >= since, ProductHistory.price.is_not(None))
        .order_by(ProductHistory.scraped_at)
    ).all()
    prices: dict[int, list[tuple[datetime, Decimal]]] = {}
    for product_id, price, at in rows:
        prices.setdefault(product_id, []).append((at, price))

    candidates = {pid: series for pid, series in prices.items() if len(series) >= 2}
    if not candidates:
        return []
    products = {
        p.id: p
        for p in db.exec(
            select(Product).where(
                Product.id.in_(list(candidates)),
                Product.available == True,  # noqa: E712
                Product.status == ProductStatus.ACTIVE,
                Product.price.is_not(None),
            )
        ).all()
    }
    deals = []
    for pid, product in products.items():
        series = candidates[pid]
        highest = max(price for _, price in series)
        lowest = min(price for _, price in series)
        current = product.price
        if highest <= 0 or current > lowest:  # only products at their window low qualify
            continue
        discount = float((highest - current) / highest * 100)
        if discount < min_discount:
            continue
        deals.append(
            {
                "product": product,
                "discount_pct": round(discount, 1),
                "was": highest,
                "now": current,
                "days": days,
            }
        )
    deals.sort(key=lambda d: (-d["discount_pct"], -(d["product"].view_count or 0)))
    return deals[:limit]
