"""Catalog filters, facets, deals, watches and alert delivery (isolated, migrated database)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app import alerts
from app.api.dependencies import get_db
from app.config import settings
from app.db import run_migrations
from app.main import app
from app.models import Product, ProductHistory, ProductStatus, Watch

WATCHER = "w" * 24
OTHER = "o" * 24
NTFY = "https://ntfy.test"


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'shop.db'}")
    run_migrations(engine)

    @contextmanager
    def scope():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(alerts, "session_scope", scope)
    yield scope
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
        yield c


def add_product(db, pid, *, name=None, brand="Nike", price="100.00", sizes=("40",), available=True, **fields):
    with db() as s:
        s.add(
            Product(
                id=pid,
                slug=f"p-{pid}",
                url=f"https://www.tivolli.com.br/p-{pid}",
                name=name or f"Produto {pid}",
                brand=brand,
                price=Decimal(price),
                sizes=list(sizes),
                available=available,
                **fields,
            )
        )
        s.commit()


def add_history(db, pid, points):
    now = datetime.now(UTC)
    with db() as s:
        for days_ago, price in points:
            s.add(
                ProductHistory(
                    product_id=pid, price=Decimal(price), available=True, scraped_at=now - timedelta(days=days_ago)
                )
            )
        s.commit()


# ---- catalog and facets --------------------------------------------------------------------


def test_catalog_filters_sorts_and_pages(client, db):
    add_product(db, 1, brand="Nike", price="300.00", sizes=("38", "40"))
    add_product(db, 2, brand="Adidas", price="150.00", sizes=("40", "42"))
    add_product(db, 3, brand="Nike", price="90.00", sizes=("42",))
    add_product(db, 4, brand="Nike", price="50.00", available=False)
    add_product(db, 5, brand="Nike", price="10.00", status=ProductStatus.DISAPPEARED)

    default = client.get("/api/catalog?sort=price_asc").json()
    assert [p["id"] for p in default["items"]] == [3, 2, 1]  # sold out and disappeared are hidden
    assert default["total"] == 3

    assert {p["id"] for p in client.get("/api/catalog?brand=Nike").json()["items"]} == {1, 3}
    assert {p["id"] for p in client.get("/api/catalog?size=40").json()["items"]} == {1, 2}
    assert {p["id"] for p in client.get("/api/catalog?min_price=100&max_price=200").json()["items"]} == {2}
    assert {p["id"] for p in client.get("/api/catalog?in_stock=false").json()["items"]} == {1, 2, 3, 4}

    page = client.get("/api/catalog?sort=price_desc&limit=2&offset=2").json()
    assert [p["id"] for p in page["items"]] == [3] and page["total"] == 3 and page["offset"] == 2
    assert client.get("/api/catalog?sort=nonsense").status_code == 422


def test_catalog_text_search_matches_name(client, db):
    add_product(db, 1, name="Tênis Nike Pegasus")
    add_product(db, 2, name="Camisa Flamengo")
    found = client.get("/api/catalog?q=camisa").json()["items"]
    assert [p["id"] for p in found] == [2]


def test_facets_list_brands_sizes_and_price_range(client, db):
    add_product(db, 1, brand="Nike", price="300.00", sizes=("38", "40", "M"))
    add_product(db, 2, brand="Nike", price="150.00", sizes=("40", "9.5"))
    add_product(db, 3, brand="Adidas", price="90.00", sizes=("P",), available=False)
    data = client.get("/api/facets").json()
    assert data["brands"][0] == {"brand": "Nike", "count": 2}
    assert [s["size"] for s in data["sizes"]] == ["9.5", "38", "40", "M"]  # numbers first, sold-out sizes absent
    assert data["price"] == {"min": 90.0, "max": 300.0}


# ---- deals ---------------------------------------------------------------------------------


def test_deals_only_include_real_drops_at_the_window_low(client, db):
    add_product(db, 1, price="80.00")  # 100 -> 80: -20 %, at its low
    add_history(db, 1, [(60, "100.00"), (30, "100.00"), (1, "80.00")])
    add_product(db, 2, price="95.00")  # dropped only 5 %... and is above its low
    add_history(db, 2, [(60, "100.00"), (30, "90.00"), (1, "95.00")])
    add_product(db, 3, price="99.00")  # drop below the minimum discount
    add_history(db, 3, [(60, "100.00"), (1, "99.00")])
    add_product(db, 4, price="50.00", available=False)  # sold out
    add_history(db, 4, [(60, "100.00"), (1, "50.00")])
    add_product(db, 5, price="100.00")  # never changed: one history row
    add_history(db, 5, [(60, "100.00")])

    deals = client.get("/api/deals").json()["deals"]
    assert [d["product"]["id"] for d in deals] == [1]
    assert deals[0]["discount_pct"] == 20.0 and deals[0]["was"] == 100.0 and deals[0]["now"] == 80.0


def test_chat_deals_command_lists_real_deals(client, db):
    add_product(db, 1, price="70.00")
    add_history(db, 1, [(40, "100.00"), (1, "70.00")])
    data = client.post("/api/chat", json={"message": "tem alguma oferta?", "session_id": "deals-s"}).json()
    assert [p["id"] for p in data["products"]] == [1]
    assert "-30%" in data["reply"]


# ---- watches API ---------------------------------------------------------------------------


@pytest.fixture
def alerts_on(monkeypatch):
    monkeypatch.setattr(settings, "alerts_enabled", True)
    monkeypatch.setattr(settings, "alerts_ntfy_server", NTFY)
    monkeypatch.setattr(settings, "alerts_webhook_hosts", "hooks.example.com")


def _watch(client, *, pid=1, watcher=WATCHER, **body):
    payload = {"product_id": pid, "channel": "ntfy", "destination": "my-secret-topic-1"} | body
    return client.post("/api/watches", json=payload, headers={"X-Watcher-Id": watcher})


def test_watches_are_disabled_unless_alerts_are_enabled(client, db):
    add_product(db, 1)
    assert client.get("/api/alerts/config").json() == {"enabled": False, "channels": []}
    assert _watch(client).status_code == 503


def test_create_list_and_delete_a_watch(client, db, alerts_on):
    add_product(db, 1, price="100.00")
    assert client.get("/api/alerts/config").json()["channels"] == ["ntfy", "webhook"]
    created = _watch(client, size="40", target_price="80").json()
    assert created["destination"] == "my-…" and created["size"] == "40" and created["target_price"] == 80.0

    listed = client.get("/api/watches", headers={"X-Watcher-Id": WATCHER}).json()["watches"]
    assert [w["id"] for w in listed] == [created["id"]]
    assert client.get("/api/watches", headers={"X-Watcher-Id": OTHER}).json()["watches"] == []

    assert client.delete(f"/api/watches/{created['id']}", headers={"X-Watcher-Id": OTHER}).status_code == 404
    assert client.delete(f"/api/watches/{created['id']}", headers={"X-Watcher-Id": WATCHER}).status_code == 204
    assert client.get("/api/watches", headers={"X-Watcher-Id": WATCHER}).json()["watches"] == []


def test_watch_validation(client, db, alerts_on, monkeypatch):
    add_product(db, 1)
    assert (
        client.post("/api/watches", json={"product_id": 1, "channel": "ntfy", "destination": "x" * 10}).status_code
        == 401
    )
    assert _watch(client, watcher="short").status_code == 401
    assert _watch(client, pid=99).status_code == 404
    assert _watch(client, destination="bad topic!").status_code == 422
    assert _watch(client, channel="sms", destination="123").status_code == 422
    assert _watch(client, channel="webhook", destination="https://evil.example.org/x").status_code == 422
    assert _watch(client, channel="webhook", destination="https://127.0.0.1/x").status_code == 422
    assert _watch(client, channel="webhook", destination="https://hooks.example.com/abc").status_code == 201
    monkeypatch.setattr(settings, "alerts_max_watches_per_watcher", 1)
    add_product(db, 2)
    assert _watch(client, pid=2).status_code == 409


def test_same_product_and_size_updates_instead_of_duplicating(client, db, alerts_on):
    add_product(db, 1)
    _watch(client)
    _watch(client, destination="another-topic-99")
    watches = client.get("/api/watches", headers={"X-Watcher-Id": WATCHER}).json()["watches"]
    assert len(watches) == 1 and watches[0]["destination"] == "ano…"


# ---- alert delivery ------------------------------------------------------------------------


async def _rescrape(db, pid, **changes):
    with db() as s:
        p = s.get(Product, pid)
        for k, v in changes.items():
            setattr(p, k, Decimal(v) if k == "price" else v)
        s.add(p)
        s.commit()
        s.refresh(p)
    return await alerts.process(p)


def _state(db):
    with db() as s:
        return s.exec(select(Watch)).one()


@pytest.mark.asyncio
async def test_price_drop_notifies_once_and_then_follows_the_new_price(db, alerts_on):
    add_product(db, 1, price="100.00")
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="ntfy",
                destination="my-secret-topic-1",
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.commit()
    with respx.mock(assert_all_called=False) as router:
        ntfy = router.post(NTFY).mock(return_value=httpx.Response(200))
        assert await _rescrape(db, 1, price="110.00") == 0  # a rise is silent
        assert await _rescrape(db, 1, price="90.00") == 1  # a drop below the last seen price
        assert await _rescrape(db, 1, price="90.00") == 0  # the same price again: nothing
        assert ntfy.call_count == 1
        body = ntfy.calls[0].request.content.decode()
    assert "my-secret-topic-1" in body and "Baixou de preço" in body and "R$ 90,00" in body
    assert _state(db).baseline_price == Decimal("90.00") and _state(db).last_notified_at is not None


@pytest.mark.asyncio
async def test_target_price_waits_for_the_price_to_reach_it(db, alerts_on):
    add_product(db, 1, price="100.00")
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="ntfy",
                destination="my-secret-topic-1",
                target_price=Decimal("80"),
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.commit()
    with respx.mock(assert_all_called=False) as router:
        ntfy = router.post(NTFY).mock(return_value=httpx.Response(200))
        assert await _rescrape(db, 1, price="90.00") == 0  # dropped, but still above the target
        assert await _rescrape(db, 1, price="79.00") == 1
        assert ntfy.call_count == 1


@pytest.mark.asyncio
async def test_restock_and_size_back_in_stock(db, alerts_on):
    add_product(db, 1, price="100.00", sizes=("40",), available=True)
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="ntfy",
                destination="my-secret-topic-1",
                size="42",
                baseline_price=Decimal("100.00"),
                last_available=False,
            )
        )
        s.commit()
    with respx.mock(assert_all_called=False) as router:
        ntfy = router.post(NTFY).mock(return_value=httpx.Response(200))
        assert await _rescrape(db, 1, sizes=["40"]) == 0  # size 42 still missing
        assert await _rescrape(db, 1, sizes=["40", "42"]) == 1  # back in stock
        assert await _rescrape(db, 1, sizes=["40", "42"]) == 0
        assert await _rescrape(db, 1, sizes=["40"]) == 0  # gone again: state follows, no message
        assert await _rescrape(db, 1, sizes=["40", "42"]) == 1  # and back once more
    assert (
        "Voltou ao estoque" in ntfy.calls[0].request.content.decode()
        and "tamanho 42" in ntfy.calls[0].request.content.decode()
    )


@pytest.mark.asyncio
async def test_failed_delivery_is_retried_on_the_next_scrape(db, alerts_on):
    add_product(db, 1, price="100.00")
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="ntfy",
                destination="my-secret-topic-1",
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.commit()
    with respx.mock(assert_all_called=False) as router:
        router.post(NTFY).mock(return_value=httpx.Response(500))
        assert await _rescrape(db, 1, price="90.00") == 0
        assert _state(db).baseline_price == Decimal("100.00")  # kept, so the drop is still pending
        router.post(NTFY).mock(return_value=httpx.Response(200))
        assert await _rescrape(db, 1, price="90.00") == 1


@pytest.mark.asyncio
async def test_alerts_do_nothing_when_disabled(db, monkeypatch):
    monkeypatch.setattr(settings, "alerts_enabled", False)
    add_product(db, 1, price="100.00")
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="ntfy",
                destination="my-secret-topic-1",
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.commit()
    assert await _rescrape(db, 1, price="10.00") == 0


@pytest.mark.asyncio
async def test_webhook_only_reaches_an_allow_listed_host(db, alerts_on):
    add_product(db, 1, price="100.00")
    with db() as s:
        s.add(
            Watch(
                watcher_id=WATCHER,
                product_id=1,
                channel="webhook",
                destination="https://hooks.example.com/abc",
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.add(
            Watch(
                watcher_id=OTHER,
                product_id=1,
                channel="webhook",
                destination="https://internal.corp/steal",
                baseline_price=Decimal("100.00"),
                last_available=True,
            )
        )
        s.commit()
    with respx.mock(assert_all_called=False) as router:
        good = router.post("https://hooks.example.com/abc").mock(return_value=httpx.Response(200))
        bad = router.post("https://internal.corp/steal").mock(return_value=httpx.Response(200))
        assert await _rescrape(db, 1, price="90.00") == 1
    assert good.call_count == 1 and bad.call_count == 0
    sent = good.calls[0].request
    assert b"price_drop" in sent.content and b'"text"' in sent.content
