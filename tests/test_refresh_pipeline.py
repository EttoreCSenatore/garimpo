"""End-to-end refresh jobs with mocked HTTP: sitemap -> listings -> product pages -> database."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from sqlmodel import select

from app import tasks
from app.config import settings
from app.db import init_db, session_scope
from app.models import Category, Product, ProductHistory, ProductStatus, ScrapeRun

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://www.tivolli.com.br"
SITEMAP = (
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    f"<url><loc>{BASE}/esportes/futebol</loc></url></urlset>"
)
CHUTEIRA = f"{BASE}/chuteira-demo-pro-fg-9001"
CAMISA = f"{BASE}/camisa-demo-treino-9002"
EMPTY_PAGE = "<html><body></body></html>"
IDS = (9001, 9002)


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _fast_isolated_env(monkeypatch):
    """No throttling or retries, and every row the test creates is removed afterwards."""
    monkeypatch.setattr(settings, "jitter_min_ms", 0)
    monkeypatch.setattr(settings, "jitter_max_ms", 0)
    monkeypatch.setattr(settings, "requests_per_second", 1000.0)
    monkeypatch.setattr(settings, "max_retries", 0)
    init_db()
    with session_scope() as s:
        last_run = s.exec(select(ScrapeRun.id).order_by(ScrapeRun.id.desc())).first() or 0
    yield
    with session_scope() as s:
        for model, column in ((ProductHistory, ProductHistory.product_id), (Product, Product.id)):
            for row in s.exec(select(model).where(column.in_(IDS))).all():
                s.delete(row)
        for cat in s.exec(select(Category).where(Category.slug == "esportes/futebol")).all():
            s.delete(cat)
        for run in s.exec(select(ScrapeRun).where(ScrapeRun.id > last_run)).all():
            s.delete(run)
        s.commit()


def _latest_run() -> ScrapeRun:
    with session_scope() as s:
        return s.exec(select(ScrapeRun).order_by(ScrapeRun.id.desc())).first()


def _product(pid: int) -> Product:
    with session_scope() as s:
        return s.get(Product, pid)


def _mock_catalog(router: respx.MockRouter, *, chuteira=None, camisa=None) -> None:
    router.get(f"{BASE}/google_sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    router.get(f"{BASE}/esportes/futebol?p=1").mock(return_value=httpx.Response(200, text=_html("listing_demo.html")))
    router.get(f"{BASE}/esportes/futebol?p=2").mock(return_value=httpx.Response(200, text=EMPTY_PAGE))
    router.get(CHUTEIRA).mock(return_value=chuteira or httpx.Response(200, text=_html("product_chuteira_demo.html")))
    router.get(CAMISA).mock(return_value=camisa or httpx.Response(200, text=_html("product_camisa_demo.html")))


async def test_full_refresh_stores_catalog_and_records_the_run():
    with respx.mock(assert_all_called=False) as router:
        _mock_catalog(router)
        await tasks.run_full_refresh_async()

    run = _latest_run()
    assert (run.run_type, run.status) == ("full", "completed")
    assert (run.products_scraped, run.products_failed, run.products_disappeared) == (2, 0, 0)
    assert run.completed_at is not None

    chuteira, camisa = _product(9001), _product(9002)
    assert chuteira.price == Decimal("1899.90") and chuteira.available
    assert camisa.price == Decimal("149.90") and camisa.sizes == ["P", "M"]
    with session_scope() as s:
        category = s.exec(select(Category).where(Category.slug == "esportes/futebol")).one()
        assert category.product_count == 2
        assert chuteira.category_id == camisa.category_id == category.id
        assert len(s.exec(select(ProductHistory).where(ProductHistory.product_id.in_(IDS))).all()) == 2


async def test_second_full_refresh_counts_disappeared_and_failed_products():
    with respx.mock(assert_all_called=False) as router:
        _mock_catalog(router)
        await tasks.run_full_refresh_async()
    with respx.mock(assert_all_called=False) as router:
        _mock_catalog(router, chuteira=httpx.Response(404), camisa=httpx.Response(500))
        await tasks.run_full_refresh_async()

    run = _latest_run()
    assert run.status == "completed"
    assert (run.products_scraped, run.products_failed, run.products_disappeared) == (0, 1, 1)
    assert _product(9001).status == ProductStatus.DISAPPEARED
    # A failed fetch must not wipe what we already know.
    assert _product(9002).price == Decimal("149.90")


async def test_full_refresh_marks_the_run_failed_when_the_sitemap_is_down():
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{BASE}/google_sitemap.xml").mock(return_value=httpx.Response(503))
        await tasks.run_full_refresh_async()

    run = _latest_run()
    assert run.status == "failed" and run.completed_at is not None
    assert "503" in run.error_message
    assert tasks.active_workers["full"] == 0  # the worker counter is released on failure


async def test_incremental_refresh_records_price_change_in_history():
    tasks._save_product(
        {
            "id": 9002,
            "slug": "camisa-demo-treino",
            "url": CAMISA,
            "name": "Camisa Demo Treino",
            "price": Decimal("999.00"),
            "available": True,
            "status": ProductStatus.ACTIVE,
        }
    )
    with respx.mock(assert_all_called=False) as router:
        router.get(CAMISA).mock(return_value=httpx.Response(200, text=_html("product_camisa_demo.html")))
        await tasks.run_incremental_refresh_async()

    run = _latest_run()
    assert (run.run_type, run.status) == ("incremental", "completed")
    assert run.products_scraped >= 1
    assert _product(9002).price == Decimal("149.90")
    with session_scope() as s:
        prices = [
            h.price
            for h in s.exec(
                select(ProductHistory).where(ProductHistory.product_id == 9002).order_by(ProductHistory.id)
            ).all()
        ]
    assert prices == [Decimal("999.00"), Decimal("149.90")]
