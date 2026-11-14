from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import structlog
from sqlmodel import Session, select, func

from app.db import engine, init_db, session_scope
from app.models import Category, Product, ProductStatus, ScrapeRun
from app.scraper.client import RateLimitedClient
from app.scraper.listings import crawl_category
from app.scraper.products import fetch_and_parse_product, infer_brand
from app.tasks import _save_product

logger = structlog.get_logger()

# Categorias populares para semear produtos reais — cobre os principais
# tipos de produto da loja (calçados, camisas, bolas, raquetes, fitness,
# agasalhos, chinelos e acessórios), não apenas tênis.
TARGET_CATEGORIES = [
    # Calçados
    (144, "running-masculino"),
    (143, "running-feminino"),
    (93, "chuteiras-para-campo"),
    (94, "chuteiras-society"),
    (205, "all-star-converse"),
    # Camisas / vestuário
    (96, "camisa-de-times-nacionais"),
    (97, "camisa-de-times-internacionais"),
    (258, "camisa-times-europeus-champions-league"),
    (118, "camisa-de-selecoes"),
    (234, "agasalhosjaquetas"),
    (220, "fitness"),
    # Tênis (esporte): raquetes e cordas
    (92, "tenis"),
    # Bolas
    (172, "bolas"),
    (102, "bolas-para-campo"),
    # Chinelos e acessórios
    (173, "chinelo"),
    (165, "acessorios"),
    (127, "mochilas"),
]


async def seed_real_products_from_tivolli(max_per_category: int = 10) -> int:
    init_db()
    client = RateLimitedClient()
    saved_count = 0
    now = datetime.now(timezone.utc)

    # First delete any synthetic seed products with IDs < 10000
    with session_scope() as session:
        synthetic = session.exec(select(Product).where(Product.id < 10000)).all()
        for p in synthetic:
            session.delete(p)
        session.commit()
        if synthetic:
            logger.info("seed.removed_synthetic", count=len(synthetic))

    try:
        for cat_id, cat_slug in TARGET_CATEGORIES:
            urls = await crawl_category(cat_id, cat_slug, client, max_pages=1)
            logger.info("seed.crawled_category", category=cat_slug, found_urls=len(urls))
            
            for url in urls[:max_per_category]:
                try:
                    data = await fetch_and_parse_product(client, url, cat_id)
                    if data and data.get("name"):
                        data["brand"] = infer_brand(data["name"], data.get("codigo"))
                        # Ensure protocol relative images have https:
                        data["images"] = [
                            ("https:" + img if img.startswith("//") else img)
                            for img in data.get("images", [])
                        ]
                        saved_product, changed = _save_product(data)
                        if saved_product:
                            saved_count += 1
                            logger.info(
                                "seed.saved_real_product",
                                id=saved_product.id,
                                name=saved_product.name[:40],
                                price=str(saved_product.price),
                                brand=saved_product.brand,
                            )
                except Exception as e:
                    logger.error("seed.product_error", url=url, error=str(e))

        # Record scrape run
        with session_scope() as session:
            run = ScrapeRun(
                run_type="seed_real",
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                products_scraped=saved_count,
                products_failed=0,
                products_disappeared=0,
                status="completed",
            )
            session.add(run)
            session.commit()

        logger.info("seed.completed", total_saved=saved_count)
        return saved_count
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(seed_real_products_from_tivolli())
