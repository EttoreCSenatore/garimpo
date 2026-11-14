from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from sqlmodel import select

from app.db import init_db, session_scope
from app.models import ProductHistory, ProductStatus, ScrapeRun
from app.scraper.products import infer_brand
from app.splunk_hec import SplunkHECLogger


@pytest.fixture
def hec(tmp_path):
    return SplunkHECLogger(
        url="https://localhost:8088/services/collector/event",
        token="t",
        batch_size=2,
        verify_ssl=True,
        buffer_file=str(tmp_path / "events.jsonl"),
        buffer_max_lines=100,
    )


def _lines(path: str) -> list[dict]:
    p = Path(path)
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


@pytest.mark.asyncio
async def test_hec_failed_events_are_buffered_once_not_duplicated(hec):
    with respx.mock(assert_all_called=False) as mock:
        mock.post(hec.url).mock(return_value=httpx.Response(400))
        for i in range(3):
            await hec.send({"event_type": "e", "id": i})
        await hec.flush()
        await hec.flush()
        await hec.send({"event_type": "e", "id": 99})
        await hec.flush()
    ids = [e["event"]["id"] for e in _lines(hec.buffer_file)]
    assert sorted(ids) == [0, 1, 2, 99]


@pytest.mark.asyncio
async def test_hec_buffer_is_drained_after_recovery(hec):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(hec.url).mock(return_value=httpx.Response(400))
        await hec.send({"event_type": "e", "id": 1})
        await hec.flush()
        assert len(_lines(hec.buffer_file)) == 1
        route.mock(return_value=httpx.Response(200, json={"text": "Success"}))
        await hec.flush()
        await hec.send({"event_type": "e", "id": 2})
        await hec.flush()
    assert _lines(hec.buffer_file) == []
    assert not Path(hec.buffer_file).exists()


@pytest.mark.asyncio
async def test_hec_skips_corrupt_buffer_lines(hec):
    Path(hec.buffer_file).write_text('{"event": {"id": 1}}\nnot json\n{"event": {"id": 2}}\n')
    assert [e["event"]["id"] for e in hec._read_buffer_file()] == [1, 2]


def test_hec_buffer_cap_keeps_newest(hec):
    hec.buffer_max_lines = 3
    hec._write_buffer_file([{"event": {"id": i}} for i in range(10)])
    assert [e["event"]["id"] for e in _lines(hec.buffer_file)] == [7, 8, 9]


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
