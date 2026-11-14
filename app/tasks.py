from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.models import Category, Product, ProductHistory, ProductStatus, ScrapeRun
from app.scraper.categories import discover_categories
from app.scraper.client import RateLimitedClient
from app.scraper.listings import crawl_category
from app.scraper.products import fetch_and_parse_product, infer_brand
from app.splunk_hec import get_hec_logger
from app.state import active_workers, get_run_lock, inflight_single

logger = structlog.get_logger()


def _save_product(data: dict) -> tuple[Product, bool]:
    product_id = data["id"]
    changed = False
    with session_scope() as session:
        existing = session.get(Product, product_id)
        now = datetime.now(UTC)

        if data.get("status") == ProductStatus.DISAPPEARED:
            if existing:
                if existing.status != ProductStatus.DISAPPEARED:
                    changed = True
                existing.status = ProductStatus.DISAPPEARED
                existing.updated_at = now
                session.add(existing)
                session.commit()
                return existing, changed
            return None, changed

        history_entry = ProductHistory(
            product_id=product_id,
            price=data.get("price"),
            price_boleto=data.get("price_boleto"),
            available=data.get("available", False),
            status=data.get("status", ProductStatus.ACTIVE),
            scraped_at=data.get("scraped_at", now),
        )
        session.add(history_entry)

        if existing:
            if existing.price != data.get("price") or existing.available != data.get("available"):
                changed = True
            existing.slug = data["slug"]
            existing.url = data["url"]
            existing.name = data["name"]
            existing.codigo = data.get("codigo")
            existing.currency = data.get("currency", "BRL")
            existing.price = data.get("price")
            existing.price_boleto = data.get("price_boleto")
            existing.installments = data.get("installments")
            existing.sizes = data.get("sizes", [])
            existing.available = data.get("available", False)
            existing.description = data.get("description")
            existing.images = data.get("images", [])
            existing.category_id = data.get("category_id")
            existing.breadcrumbs = data.get("breadcrumbs", [])
            existing.brand = infer_brand(data["name"], data.get("codigo"))
            existing.status = data.get("status", ProductStatus.ACTIVE)
            existing.scraped_at = data.get("scraped_at", now)
            existing.updated_at = now
            session.add(existing)
        else:
            product = Product(
                id=product_id,
                slug=data["slug"],
                url=data["url"],
                name=data["name"],
                codigo=data.get("codigo"),
                currency=data.get("currency", "BRL"),
                price=data.get("price"),
                price_boleto=data.get("price_boleto"),
                installments=data.get("installments"),
                sizes=data.get("sizes", []),
                available=data.get("available", False),
                description=data.get("description"),
                images=data.get("images", []),
                category_id=data.get("category_id"),
                breadcrumbs=data.get("breadcrumbs", []),
                brand=infer_brand(data["name"], data.get("codigo")),
                status=data.get("status", ProductStatus.ACTIVE),
                scraped_at=data.get("scraped_at", now),
            )
            session.add(product)
            changed = True

        session.commit()
        saved = session.get(Product, product_id)
        return saved, changed


async def _emit_product_events(product: Product, changed: bool, disappeared: bool = False) -> None:
    hec = get_hec_logger()
    if disappeared:
        await hec.send(
            {
                "event_type": "tivolli.product.disappeared",
                "id": product.id,
                "name": product.name,
                "url": product.url,
            }
        )
        return

    await hec.send(
        {
            "event_type": "tivolli.product.scraped",
            "id": product.id,
            "name": product.name,
            "price": str(product.price) if product.price else None,
            "available": product.available,
        }
    )

    if changed:
        await hec.send(
            {
                "event_type": "tivolli.product.updated",
                "id": product.id,
                "name": product.name,
                "new_price": str(product.price) if product.price else None,
                "new_available": product.available,
            }
        )


async def refresh_single_product_async(product_id: int) -> None:
    active_workers["single"] += 1
    client = RateLimitedClient()
    hec = get_hec_logger()
    try:
        with session_scope() as session:
            product = session.get(Product, product_id)
            if not product:
                return
            url = product.url
            category_id = product.category_id

        data = await fetch_and_parse_product(client, url, category_id)
        if data is None:
            return

        if data.get("status") == ProductStatus.DISAPPEARED:
            saved, _ = _save_product(data)
            if saved:
                await _emit_product_events(saved, False, disappeared=True)
            return

        saved, changed = _save_product(data)
        if saved:
            await _emit_product_events(saved, changed)
    except Exception as exc:
        logger.error("task.refresh_single.error", product_id=product_id, error=str(exc))
        await hec.send(
            {"event_type": "tivolli.error.http", "product_id": product_id, "error": str(exc)}
        )
    finally:
        inflight_single.discard(product_id)
        active_workers["single"] -= 1
        await client.close()


async def _run_full_refresh() -> None:
    active_workers["full"] += 1
    client = RateLimitedClient()
    hec = get_hec_logger()
    run = ScrapeRun(run_type="full", status="running")
    with session_scope() as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    scraped = 0
    failed = 0
    disappeared = 0
    start = datetime.now(UTC)

    try:
        await hec.send({"event_type": "tivolli.run.started", "run_id": run_id, "run_type": "full"})

        categories = await discover_categories(client)
        all_product_urls: list[tuple[str, int | None]] = []

        for cat in categories:
            urls = await crawl_category(cat.id, cat.slug, client)
            for u in urls:
                all_product_urls.append((u, cat.id))
            with session_scope() as session:
                c = session.get(Category, cat.id)
                if c:
                    c.product_count = len(urls)
                    c.last_seen = datetime.now(UTC)
                    session.add(c)
                    session.commit()

        seen: set[int] = set()
        for url, cat_id in all_product_urls:
            from app.scraper.products import _extract_id
            pid = _extract_id(url)
            if pid in seen:
                continue
            seen.add(pid)

            data = await fetch_and_parse_product(client, url, cat_id)
            if data is None:
                failed += 1
                continue

            if data.get("status") == ProductStatus.DISAPPEARED:
                saved, _ = _save_product(data)
                if saved:
                    disappeared += 1
                    await _emit_product_events(saved, False, disappeared=True)
                continue

            saved, changed = _save_product(data)
            if saved:
                scraped += 1
                await _emit_product_events(saved, changed)

        with session_scope() as session:
            r = session.get(ScrapeRun, run_id)
            if r:
                r.completed_at = datetime.now(UTC)
                r.products_scraped = scraped
                r.products_failed = failed
                r.products_disappeared = disappeared
                r.status = "completed"
                session.add(r)
                session.commit()

        await hec.send(
            {
                "event_type": "tivolli.run.completed",
                "run_id": run_id,
                "run_type": "full",
                "products_scraped": scraped,
                "products_failed": failed,
                "products_disappeared": disappeared,
                "duration_seconds": (datetime.now(UTC) - start).total_seconds(),
            }
        )
    except Exception as exc:
        logger.error("task.full_refresh.error", error=str(exc))
        with session_scope() as session:
            r = session.get(ScrapeRun, run_id)
            if r:
                r.completed_at = datetime.now(UTC)
                r.status = "failed"
                r.error_message = str(exc)
                session.add(r)
                session.commit()
        await hec.send(
            {"event_type": "tivolli.error.http", "run_id": run_id, "error": str(exc)}
        )
    finally:
        active_workers["full"] -= 1
        await client.close()
        await hec.flush()


async def _run_incremental_refresh() -> None:
    active_workers["incremental"] += 1
    client = RateLimitedClient()
    hec = get_hec_logger()
    run = ScrapeRun(run_type="incremental", status="running")
    with session_scope() as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    scraped = 0
    failed = 0
    start = datetime.now(UTC)

    try:
        with session_scope() as session:
            statement = (
                select(Product)
                .where(Product.status != ProductStatus.DISAPPEARED)
                .order_by(Product.view_count.desc())
                .limit(settings.incremental_top_n)
            )
            top_products = session.exec(statement).all()

        for product in top_products:
            data = await fetch_and_parse_product(client, product.url, product.category_id)
            if data is None:
                failed += 1
                continue

            if data.get("status") == ProductStatus.DISAPPEARED:
                saved, _ = _save_product(data)
                if saved:
                    await _emit_product_events(saved, False, disappeared=True)
                continue

            saved, changed = _save_product(data)
            if saved:
                scraped += 1
                await _emit_product_events(saved, changed)

        with session_scope() as session:
            r = session.get(ScrapeRun, run_id)
            if r:
                r.completed_at = datetime.now(UTC)
                r.products_scraped = scraped
                r.products_failed = failed
                r.status = "completed"
                session.add(r)
                session.commit()

        await hec.send(
            {
                "event_type": "tivolli.run.completed",
                "run_id": run_id,
                "run_type": "incremental",
                "products_scraped": scraped,
                "products_failed": failed,
                "duration_seconds": (datetime.now(UTC) - start).total_seconds(),
            }
        )
    except Exception as exc:
        logger.error("task.incremental_refresh.error", error=str(exc))
        with session_scope() as session:
            r = session.get(ScrapeRun, run_id)
            if r:
                r.completed_at = datetime.now(UTC)
                r.status = "failed"
                r.error_message = str(exc)
                session.add(r)
                session.commit()
    finally:
        active_workers["incremental"] -= 1
        await client.close()
        await hec.flush()


async def _run_exclusive(kind: str, runner) -> None:
    """Run ``runner`` unless another full/incremental refresh is already running.

    Full and incremental refreshes share one lock so the target site is never
    hit by two crawlers at once (and repeated admin triggers cannot pile up).
    """
    lock = get_run_lock("scrape")
    if lock.locked():
        logger.warning("task.refresh.skipped_already_running", kind=kind)
        return
    async with lock:
        await runner()


async def run_full_refresh_async() -> None:
    await _run_exclusive("full", _run_full_refresh)


async def run_incremental_refresh_async() -> None:
    await _run_exclusive("incremental", _run_incremental_refresh)
