"""Disappearance detection, parse-failure samples, failure spikes and retention (isolated DB)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app import failures, reconcile, retention, tasks
from app.config import settings
from app.db import run_migrations
from app.main import app
from app.models import ParseFailure, Product, ProductHistory, ProductStatus, ScrapeRun


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """A migrated throwaway database wired into every module that opens its own sessions."""
    engine = create_engine(f"sqlite:///{tmp_path / 'iso.db'}")
    run_migrations(engine)

    @contextmanager
    def scope():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    for module in (reconcile, retention, failures):
        monkeypatch.setattr(module, "session_scope", scope)
    return scope


def _add(scope, pid: int, **fields) -> None:
    with scope() as s:
        s.add(
            Product(
                id=pid,
                slug=f"p-{pid}",
                url=f"https://www.tivolli.com.br/p-{pid}",
                name=f"P{pid}",
                price=Decimal("10.00"),
                available=True,
                **fields,
            )
        )
        s.commit()


def _status(scope, pid: int) -> tuple[ProductStatus, int]:
    with scope() as s:
        p = s.get(Product, pid)
        return p.status, p.missing_crawls


def test_product_disappears_only_after_n_consecutive_missed_crawls(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "disappear_after_crawls", 3)
    for pid in (1, 2, 3):
        _add(isolated_db, pid)
    # Product 3 is missing from three crawls in a row; 1 and 2 are always listed.
    assert reconcile.reconcile_missing({1, 2}) == []
    assert _status(isolated_db, 3) == (ProductStatus.ACTIVE, 1)
    assert reconcile.reconcile_missing({1, 2}) == []
    gone = reconcile.reconcile_missing({1, 2})
    assert [p.id for p in gone] == [3]
    assert _status(isolated_db, 3)[0] == ProductStatus.DISAPPEARED
    with isolated_db() as s:
        history = s.exec(select(ProductHistory).where(ProductHistory.product_id == 3)).all()
    assert [h.status for h in history] == [ProductStatus.DISAPPEARED]


def test_reappearing_product_resets_its_counter(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "disappear_after_crawls", 3)
    for pid in (1, 2):
        _add(isolated_db, pid)
    reconcile.reconcile_missing({1})
    reconcile.reconcile_missing({1})
    assert _status(isolated_db, 2)[1] == 2
    reconcile.reconcile_missing({1, 2})
    assert _status(isolated_db, 2) == (ProductStatus.ACTIVE, 0)


def test_broken_crawl_never_wipes_the_catalog(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "disappear_after_crawls", 1)
    monkeypatch.setattr(settings, "disappear_min_ratio", 0.5)
    for pid in range(1, 11):
        _add(isolated_db, pid)
    # A crawl that sees only 2 of 10 known products is considered broken.
    assert reconcile.reconcile_missing({1, 2}) == []
    assert all(_status(isolated_db, pid) == (ProductStatus.ACTIVE, 0) for pid in range(1, 11))


def test_parse_failure_samples_are_truncated_and_pruned(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "parse_failure_samples_keep", 3)
    monkeypatch.setattr(settings, "parse_sample_bytes", 50)
    for i in range(5):
        failures.record_parse_failure(f"https://x/{i}", "ValueError: boom", http_status=200, html="<html>" + "a" * 500)
    with isolated_db() as s:
        rows = s.exec(select(ParseFailure).order_by(ParseFailure.id)).all()
    assert [r.url for r in rows] == ["https://x/2", "https://x/3", "https://x/4"]
    assert all(len(r.html_sample) == 50 for r in rows)


@pytest.mark.parametrize(
    ("scraped", "failed", "spike"),
    [(100, 5, False), (70, 30, True), (5, 4, False), (0, 0, False)],  # below the minimum is never a spike
)
def test_failure_spike_needs_enough_attempts_and_a_high_ratio(scraped, failed, spike):
    assert tasks._failure_spike(scraped, failed) is spike


def test_retention_prunes_old_finished_runs_and_optionally_history(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "retention_runs_days", 30)
    monkeypatch.setattr(settings, "retention_history_days", 0)
    now = datetime.now(UTC)
    _add(isolated_db, 1)
    with isolated_db() as s:
        s.add(ScrapeRun(run_type="full", status="completed", completed_at=now - timedelta(days=60)))
        s.add(ScrapeRun(run_type="full", status="completed", completed_at=now - timedelta(days=1)))
        s.add(ScrapeRun(run_type="full", status="running"))  # never pruned
        s.add(ProductHistory(product_id=1, price=Decimal("9"), scraped_at=now - timedelta(days=400)))
        s.commit()

    assert retention.apply_retention() == {"scrape_runs": 1, "product_history": 0}

    monkeypatch.setattr(settings, "retention_history_days", 365)
    assert retention.apply_retention()["product_history"] == 1
    with isolated_db() as s:
        assert len(s.exec(select(ScrapeRun)).all()) == 2


def test_admin_parse_failures_endpoint_needs_the_token_and_truncates(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "t" * 32)
    with TestClient(app) as client:  # startup runs the migrations that create the table
        failures.record_parse_failure("https://x/endpoint", "ValueError: nope", html="z" * 5000)
        assert client.get("/admin/parse-failures").status_code == 401
        headers = {"X-Admin-Token": "t" * 32}
        short = client.get("/admin/parse-failures?limit=100", headers=headers).json()["failures"]
        full = client.get("/admin/parse-failures?limit=100&full=true", headers=headers).json()["failures"]
    mine_short = next(f for f in short if f["url"] == "https://x/endpoint")
    mine_full = next(f for f in full if f["url"] == "https://x/endpoint")
    assert len(mine_short["html_sample"]) == 2000 and len(mine_full["html_sample"]) == 5000


@pytest.fixture
def pipeline_db(isolated_db, monkeypatch):
    """Like isolated_db, also for the refresh tasks, plus a fast, polite-free HTTP client."""
    monkeypatch.setattr(tasks, "session_scope", isolated_db)
    monkeypatch.setattr(settings, "jitter_min_ms", 0)
    monkeypatch.setattr(settings, "jitter_max_ms", 0)
    monkeypatch.setattr(settings, "requests_per_second", 1000.0)
    monkeypatch.setattr(settings, "max_retries", 0)
    return isolated_db


async def test_unparseable_page_is_a_failure_with_a_stored_sample(pipeline_db):
    import httpx
    import respx
    from test_refresh_pipeline import CAMISA, CHUTEIRA, _mock_catalog

    broken = httpx.Response(200, text="<html><body><p>redesigned page</p></body></html>")
    with respx.mock(assert_all_called=False) as router:
        _mock_catalog(router, chuteira=broken)
        await tasks.run_full_refresh_async()

    with pipeline_db() as s:
        run = s.exec(select(ScrapeRun).order_by(ScrapeRun.id.desc())).first()
        samples = s.exec(select(ParseFailure)).all()
        ids = {p.id for p in s.exec(select(Product)).all()}
    assert run.products_failed == 1 and run.products_scraped == 1
    assert [f.url for f in samples] == [CHUTEIRA]
    assert "redesigned page" in samples[0].html_sample
    assert ids == {9002} and CAMISA.endswith("9002")


async def test_product_dropped_from_listings_disappears_after_n_full_crawls(pipeline_db, monkeypatch):
    import httpx
    import respx
    from test_refresh_pipeline import BASE, CAMISA, CHUTEIRA, _html, _mock_catalog

    monkeypatch.setattr(settings, "disappear_after_crawls", 2)
    with respx.mock(assert_all_called=False) as router:
        _mock_catalog(router)
        await tasks.run_full_refresh_async()

    # The camisa stops being listed (its page still exists, so it is not a 404 disappearance).
    import re

    only_chuteira = re.sub(
        r'<li class="item product product-item">(?:(?!</li>).)*camisa-demo-treino-9002(?:(?!</li>).)*</li>',
        "",
        _html("listing_demo.html"),
    )
    assert "camisa-demo-treino-9002" not in only_chuteira
    for expected_status, expected_misses in ((ProductStatus.ACTIVE, 1), (ProductStatus.DISAPPEARED, 2)):
        with respx.mock(assert_all_called=False) as router:
            _mock_catalog(router)
            router.get(f"{BASE}/esportes/futebol?p=1").mock(return_value=httpx.Response(200, text=only_chuteira))
            router.get(CAMISA).mock(return_value=httpx.Response(200, text=_html("product_camisa_demo.html")))
            router.get(CHUTEIRA).mock(return_value=httpx.Response(200, text=_html("product_chuteira_demo.html")))
            await tasks.run_full_refresh_async()
        with pipeline_db() as s:
            camisa = s.get(Product, 9002)
        assert (camisa.status, camisa.missing_crawls) == (expected_status, expected_misses)
