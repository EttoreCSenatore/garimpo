from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, text
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_db
from app.main import app
from app.models import Product
from app.search.fts import ensure_search_index, match_all, match_any


def _product(pid: int, name: str, *, brand=None, breadcrumbs=(), description="", views=0, sizes=()):
    return Product(
        id=pid,
        slug=name.lower().replace(" ", "-"),
        url=f"https://www.tivolli.com.br/{pid}-x",
        name=name,
        brand=brand,
        breadcrumbs=list(breadcrumbs),
        description=description,
        price=Decimal("199.90"),
        available=True,
        view_count=views,
        sizes=list(sizes),
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def client(engine):
    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _add(engine, *products):
    with Session(engine) as s:
        for p in products:
            s.add(p)
        s.commit()


def _search(client, q):
    return [i["name"] for i in client.get("/products", params={"q": q}).json()["items"]]


# --- query building -------------------------------------------------------

def test_match_builders_only_emit_quoted_words():
    assert match_all('nike "air" OR NEAR(x*') == '"nike"* AND "air"* AND "or"* AND "near"* AND "x"*'
    assert match_all("%%% ---") is None
    assert match_any(["all-star", "bola"]) == '("all star"* OR "bola"*)'
    assert match_any([]) is None


# --- /products?q ----------------------------------------------------------

def test_search_ignores_accents_case_and_word_order(client, engine):
    _add(
        engine,
        _product(1, "Tênis Nike Air Max 90", brand="Nike"),
        _product(2, "Chuteira Adidas Predator", brand="Adidas"),
    )
    assert _search(client, "tenis") == ["Tênis Nike Air Max 90"]
    assert _search(client, "MAX air") == ["Tênis Nike Air Max 90"]
    assert _search(client, "chuteira predator adidas") == ["Chuteira Adidas Predator"]
    assert _search(client, "nike predator") == []


def test_search_matches_prefixes_and_other_fields(client, engine):
    _add(
        engine,
        _product(1, "Bola de Futebol Campo", breadcrumbs=["Home", "Bolas"]),
        _product(2, "Camisa Flamengo 2025", description="Camisa oficial do Clube de Regatas do Flamengo"),
    )
    assert _search(client, "bol") == ["Bola de Futebol Campo"]
    assert _search(client, "flamengo") == ["Camisa Flamengo 2025"]
    # Descriptions are not indexed: they mention other products and caused false matches.
    assert _search(client, "regatas") == []


@pytest.mark.parametrize("q", ['"', "NEAR(", "*", "a OR", ")(", "' OR 1=1 --", "%", "\\"])
def test_search_never_errors_on_fts_syntax(client, engine, q):
    _add(engine, _product(1, "Tênis Nike"))
    assert client.get("/products", params={"q": q}).status_code == 200


def test_index_follows_updates_and_deletes(client, engine):
    _add(engine, _product(1, "Tênis Velho"))
    assert _search(client, "velho") == ["Tênis Velho"]
    with Session(engine) as s:
        p = s.get(Product, 1)
        p.name = "Tênis Novo"
        p.slug = "tenis-novo"  # the slug is indexed too
        s.add(p)
        s.commit()
    assert _search(client, "velho") == []
    assert _search(client, "novo") == ["Tênis Novo"]
    with Session(engine) as s:
        s.delete(s.get(Product, 1))
        s.commit()
    assert _search(client, "novo") == []


def test_existing_rows_are_indexed_when_the_index_is_created(engine):
    _add(engine, _product(1, "Raquete Yonex Ezone"))
    assert ensure_search_index(engine)
    with engine.connect() as conn:
        hits = conn.execute(text("SELECT rowid FROM products_fts WHERE products_fts MATCH 'yonex'")).all()
    assert hits == [(1,)]


def test_view_counter_updates_do_not_touch_the_index(client, engine):
    _add(engine, _product(1, "Tênis Nike"))
    ensure_search_index(engine)
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM products_fts_data")).scalar()
    for _ in range(5):
        client.get("/products/1")
    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM products_fts_data")).scalar()
    assert before == after


def test_falls_back_to_like_without_fts(client, engine, monkeypatch):
    import app.api.routes as routes

    monkeypatch.setattr(routes, "fts_available", lambda _db: False)
    _add(engine, _product(1, "Tênis Nike Air"), _product(2, "Chuteira Adidas"))
    assert _search(client, "Nike Air") == ["Tênis Nike Air"]


# --- chat ranking -----------------------------------------------------------

def test_chat_ranks_name_matches_above_popularity(client, engine):
    _add(
        engine,
        # Very popular, but "flamengo" only appears in the description.
        _product(1, "Camisa Seleção Brasileira", description="Combina com a do Flamengo", views=500),
        _product(2, "Camisa Flamengo Oficial", views=3),
    )
    r = client.post("/api/chat", json={"message": "camisa do flamengo", "session_id": "rank-1"})
    # Clothing asks for gender first; answer it.
    r = client.post("/api/chat", json={"message": "tanto faz", "session_id": "rank-1"})
    names = [p["name"] for p in r.json()["products"]]
    assert names[0] == "Camisa Flamengo Oficial"


def test_index_with_an_older_column_layout_is_rebuilt(engine):
    _add(engine, _product(1, "Chuteira Nike Phantom"))
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE VIRTUAL TABLE products_fts USING fts5(name, brand, breadcrumbs, slug, description, "
            "content='products', content_rowid='id')"
        )
    assert ensure_search_index(engine)
    with engine.connect() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(products_fts)")]
        hits = conn.execute(text("SELECT rowid FROM products_fts WHERE products_fts MATCH 'phantom'")).all()
    assert cols == ["name", "brand", "breadcrumbs", "slug"]
    assert hits == [(1,)]
