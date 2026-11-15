from __future__ import annotations

import time
from decimal import Decimal

import pytest
from sqlmodel import select

from app.db import init_db, session_scope
from app.models import ProductHistory, ProductStatus, ScrapeRun
from app.scraper.products import infer_brand


def _product(pid: int, price: str, available: bool = True) -> dict:
    return {
        "id": pid,
        "slug": f"p-{pid}",
        "url": f"https://www.tivolli.com.br/{pid}-p",
        "name": "Tenis Nike Teste",
        "price": Decimal(price),
        "available": available,
        "status": ProductStatus.ACTIVE if available else ProductStatus.OUT_OF_STOCK,
    }


def _history_count(pid: int) -> int:
    with session_scope() as s:
        return len(s.exec(select(ProductHistory).where(ProductHistory.product_id == pid)).all())


def test_history_only_written_when_tracked_fields_change():
    from app.tasks import _save_product

    init_db()
    _save_product(_product(910001, "100.00"))
    assert _history_count(910001) == 1
    _save_product(_product(910001, "100.00"))
    _save_product(_product(910001, "100.00"))
    assert _history_count(910001) == 1
    _, changed = _save_product(_product(910001, "90.00"))
    assert changed and _history_count(910001) == 2
    _save_product(_product(910001, "90.00", available=False))
    assert _history_count(910001) == 3


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Tênis Nike Air Max", "Nike"),
        ("Raquete Head Gravity", "Head"),
        ("Overhead cable ahead", None),
        ("Tenis New Balance 574", "New Balance"),
        ("Camisa Fila Retro", "Fila"),
        ("Filamento qualquer", None),
    ],
)
def test_infer_brand_uses_word_boundaries(name, expected):
    assert infer_brand(name, None) == expected


def test_stale_running_runs_are_closed_on_startup():
    init_db()
    with session_scope() as s:
        run = ScrapeRun(run_type="full", status="running")
        s.add(run)
        s.commit()
        run_id = run.id
    init_db()
    with session_scope() as s:
        r = s.get(ScrapeRun, run_id)
        assert r.status == "failed" and r.completed_at is not None


def test_indexes_are_created():
    from app.db import engine

    init_db()
    with engine.connect() as conn:
        names = {row[1] for row in conn.exec_driver_sql("PRAGMA index_list('products')").fetchall()}
    assert {"ix_products_category_id", "ix_products_brand", "ix_products_status", "ix_products_view_count"} <= names


@pytest.mark.asyncio
async def test_request_budget_is_shared_between_clients():
    from app.scraper.client import RateLimitedClient

    a = RateLimitedClient(requests_per_second=20, jitter_min_ms=0, jitter_max_ms=0)
    b = RateLimitedClient(requests_per_second=20, jitter_min_ms=0, jitter_max_ms=0)
    start = time.monotonic()
    for _ in range(3):
        await a._throttle()
        await b._throttle()
    assert time.monotonic() - start >= 5 * 0.05 * 0.9  # 6 calls => at least 5 intervals of 50 ms
    await a.close()
    await b.close()


@pytest.mark.asyncio
async def test_refresh_runs_do_not_overlap(monkeypatch):
    import asyncio

    from app import tasks

    started = 0
    gate = asyncio.Event()

    async def slow() -> None:
        nonlocal started
        started += 1
        await gate.wait()

    first = asyncio.create_task(tasks._run_exclusive("full", slow))
    await asyncio.sleep(0.01)
    await tasks._run_exclusive("incremental", slow)  # skipped: lock held
    gate.set()
    await first
    assert started == 1
