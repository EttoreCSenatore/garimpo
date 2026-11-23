"""Disappearance detection from full crawls.

A 404 on a product page is not the only way a product goes away: it can simply stop being listed.
After each full crawl, products missing from every listing get a counter; at
``disappear_after_crawls`` consecutive misses they are marked disappeared. A crawl that finds
too few of the known products is treated as broken, so a site outage never wipes the catalog.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.events import emit
from app.models import Product, ProductHistory, ProductStatus


def reconcile_missing(seen_ids: set[int]) -> list[Product]:
    """Update missing-crawl counters from the ids seen in listings; return the newly disappeared."""
    newly: list[Product] = []
    with session_scope() as session:
        known = session.exec(select(Product).where(Product.status != ProductStatus.DISAPPEARED)).all()
        if not known:
            return newly
        found = sum(1 for p in known if p.id in seen_ids)
        if found / len(known) < settings.disappear_min_ratio:
            emit(
                {
                    "event_type": "garimpo.error.crawl_incomplete",
                    "known_products": len(known),
                    "seen_in_listings": found,
                }
            )
            return newly

        now = datetime.now(UTC)
        for product in known:
            if product.id in seen_ids:
                if product.missing_crawls:
                    product.missing_crawls = 0
                    session.add(product)
                continue
            product.missing_crawls += 1
            if product.missing_crawls >= settings.disappear_after_crawls:
                product.status = ProductStatus.DISAPPEARED
                product.available = False
                product.updated_at = now
                session.add(
                    ProductHistory(
                        product_id=product.id,
                        price=product.price,
                        price_boleto=product.price_boleto,
                        available=False,
                        status=ProductStatus.DISAPPEARED,
                        scraped_at=now,
                    )
                )
                newly.append(product)
            session.add(product)
        session.commit()
        for product in newly:
            session.refresh(product)
    return newly
