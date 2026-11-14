from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_db
from app.config import settings
from app.main import app
from app.models import Category, Product, ProductStatus


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_products(session: Session, count: int = 5):
    category = Category(id=1, slug="calcados", url="/c/1-calcados", name="Calçados")
    session.add(category)
    for i in range(count):
        product = Product(
            id=1000 + i,
            slug=f"produto-{i}",
            url=f"https://www.tivolli.com.br/{1000 + i}-produto-{i}",
            name=f"Produto Teste {i}",
            codigo=f"CODE{i:04d}",
            currency="BRL",
            price=Decimal("100.00") + i * 10,
            price_boleto=Decimal("90.00") + i * 10,
            sizes=["38", "39", "40"],
            available=True if i % 2 == 0 else False,
            description=f"Descrição do produto {i}",
            images=[f"https://example.com/img{i}.jpg"],
            category_id=1,
            breadcrumbs=["Calçados", "Tênis"],
            brand="Nike" if i % 2 == 0 else "Adidas",
            status=ProductStatus.ACTIVE,
            scraped_at=datetime.now(UTC),
        )
        session.add(product)
    session.commit()


def test_health_check(client, db_session):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "tivolli-scraper"
    assert "timestamp" in data


def test_list_products_empty(client, db_session):
    response = client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_products_pagination(client, db_session):
    _seed_products(db_session, count=10)

    response = client.get("/products?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 10
    assert data["next_cursor"] is not None

    cursor = data["next_cursor"]
    response2 = client.get(f"/products?limit=3&cursor={cursor}")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 3
    assert data2["items"][0]["id"] > data["items"][-1]["id"]

    response_last = client.get(f"/products?limit=3&cursor={data2['next_cursor']}")
    data_last = response_last.json()
    assert len(data_last["items"]) == 3
    if data_last["next_cursor"]:
        response_final = client.get(f"/products?limit=3&cursor={data_last['next_cursor']}")
        data_final = response_final.json()
        assert len(data_final["items"]) == 1
        assert data_final["next_cursor"] is None


def test_list_products_filter_by_brand(client, db_session):
    _seed_products(db_session, count=6)
    response = client.get("/products?brand=Nike")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["brand"] == "Nike"


def test_list_products_filter_by_price(client, db_session):
    _seed_products(db_session, count=5)
    response = client.get("/products?min_price=120&max_price=140")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert 120 <= float(item["price"]) <= 140


def test_list_products_filter_by_availability(client, db_session):
    _seed_products(db_session, count=6)
    response = client.get("/products?available=true")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["available"] is True


def test_list_products_search(client, db_session):
    _seed_products(db_session, count=5)
    response = client.get("/products?q=Produto Teste 0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1


def test_get_single_product(client, db_session):
    _seed_products(db_session, count=1)
    response = client.get("/products/1000")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1000
    assert data["name"] == "Produto Teste 0"


def test_get_single_product_not_found(client, db_session):
    response = client.get("/products/99999")
    assert response.status_code == 404


def test_get_product_history(client, db_session):
    _seed_products(db_session, count=1)
    response = client.get("/products/1000/history")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1000
    assert "history" in data


def test_list_categories(client, db_session):
    category = Category(id=1, slug="calcados", url="/c/1-calcados", name="Calçados", product_count=5)
    db_session.add(category)
    db_session.commit()

    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Calçados"


def test_stats(client, db_session):
    _seed_products(db_session, count=3)
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_products"] == 3
    assert "active_products" in data


def test_admin_refresh_requires_token(client, db_session):
    response = client.post("/admin/refresh")
    assert response.status_code == 401


def test_admin_refresh_with_token(client, db_session, monkeypatch):
    import app.tasks

    async def fake_refresh() -> None:  # never scrape the real site from tests
        return None

    monkeypatch.setattr(app.tasks, "run_full_refresh_async", fake_refresh)
    monkeypatch.setattr(settings, "admin_token", "test-token")
    response = client.post("/admin/refresh", headers={"X-Admin-Token": "test-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "started"


def test_admin_queue_requires_token(client, db_session):
    response = client.get("/admin/queue")
    assert response.status_code == 401


def test_cache_headers(client, db_session):
    _seed_products(db_session, count=1)
    response = client.get("/products")
    assert "cache-control" in response.headers
    assert "max-age" in response.headers["cache-control"]


def test_disclaimer_mode(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "disclaimer", True)
    _seed_products(db_session, count=1)
    response = client.get("/products/1000")
    data = response.json()
    assert data.get("price_disclaimer") == "indicative"
    assert "source_url" in data


def test_intent_parser():
    from app.search.intent_parser import parse_intent

    intent = parse_intent("running shoes nike under 500 in stock")
    assert "running" in intent.category_keywords
    assert intent.brand == "Nike"
    assert intent.price_max == 500.0
    assert intent.available is True

    intent_pt = parse_intent("chuteiras adidas abaixo de 300 disponível")
    assert "futebol" in intent_pt.category_keywords
    assert intent_pt.brand == "Adidas"
    assert intent_pt.price_max == 300.0
    assert intent_pt.available is True


def test_chat_endpoint(client, db_session):
    _seed_products(db_session, count=6)
    response = client.post("/api/chat", json={"message": "nike under 500"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "filters_applied" in data
    assert "products" in data
    assert data["filters_applied"].get("brand") == "Nike"
    assert len(data["products"]) > 0


def test_chat_endpoint_empty_match(client, db_session):
    response = client.post("/api/chat", json={"message": "unknownbrandunder 10"})
    assert response.status_code == 200
    data = response.json()
    assert "Não encontrei" in data["reply"]
    assert len(data["products"]) == 0


def _seed_personalized_products(session: Session):
    """Produtos com gênero/tamanho distintos para testar preferências."""
    session.add(Category(id=2, slug="calcados", url="/c/2-calcados", name="Calçados"))
    items = [
        (3001, "Tênis A Feminino", ["37", "38"]),
        (3002, "Tênis B Masculino", ["38", "39"]),
        (3003, "Tênis C Feminino", ["39", "40"]),
        (3004, "Tênis D Infantil", ["28", "30"]),
    ]
    for pid, name, sizes in items:
        product = Product(
            id=pid,
            slug=name.lower().replace(" ", "-"),
            url=f"https://www.tivolli.com.br/{pid}-{name.lower().replace(' ', '-')}",
            name=name,
            currency="BRL",
            price=Decimal("200.00"),
            sizes=sizes,
            available=True,
            images=[],
            category_id=2,
            breadcrumbs=["Calçados"],
            brand="Nike",
            status=ProductStatus.ACTIVE,
            scraped_at=datetime.now(UTC),
        )
        session.add(product)
    session.commit()


def test_intent_parser_personal_preferences():
    from app.search.intent_parser import parse_intent

    intent = parse_intent("tênis feminino tamanho 38")
    assert intent.gender == "feminino"
    assert intent.size == 38

    intent = parse_intent("para homem, número 42")
    assert intent.gender == "masculino"
    assert intent.size == 42

    intent = parse_intent("chuteira nike 40")
    assert intent.size == 40

    intent = parse_intent("tanto faz")
    assert intent.skip_preferences is True

    # Preço não deve virar tamanho
    intent = parse_intent("tênis até 500")
    assert intent.size is None
    assert intent.price_max == 500.0


def test_chat_guided_flow_personal_preferences(client, db_session):
    """O bot pergunta gênero e número antes de buscar calçados."""
    _seed_personalized_products(db_session)
    sid = "test-flow-1"

    r1 = client.post("/api/chat", json={"message": "quero um tênis", "session_id": sid})
    d1 = r1.json()
    assert r1.status_code == 200
    assert d1["products"] == []
    assert "masculino" in d1["reply"]

    r2 = client.post("/api/chat", json={"message": "feminino", "session_id": sid})
    d2 = r2.json()
    assert d2["products"] == []
    assert "número" in d2["reply"].lower()
    assert d2["filters_applied"]["gender"] == "feminino"

    r3 = client.post("/api/chat", json={"message": "38", "session_id": sid})
    d3 = r3.json()
    assert [p["id"] for p in d3["products"]] == [3001]
    assert d3["filters_applied"]["gender"] == "feminino"
    assert d3["filters_applied"]["size"] == 38
    assert "para **mulher**" in d3["reply"]
    assert "número 38" in d3["reply"]


def test_chat_preferences_in_single_message(client, db_session):
    """Informações pessoais numa mensagem só pesquisam direto."""
    _seed_personalized_products(db_session)

    response = client.post(
        "/api/chat",
        json={"message": "tênis feminino tamanho 38", "session_id": "one-shot"},
    )
    assert response.status_code == 200
    data = response.json()
    assert [p["id"] for p in data["products"]] == [3001]
    assert data["filters_applied"]["gender"] == "feminino"
    assert data["filters_applied"]["size"] == 38


def test_chat_guided_flow_skip_preferences(client, db_session):
    """'Tanto faz' dispensa as perguntas e busca sem o filtro."""
    _seed_personalized_products(db_session)
    sid = "test-flow-2"

    r1 = client.post("/api/chat", json={"message": "quero um tênis", "session_id": sid})
    assert r1.json()["products"] == []

    r2 = client.post("/api/chat", json={"message": "tanto faz", "session_id": sid})
    assert "número" in r2.json()["reply"].lower()

    r3 = client.post("/api/chat", json={"message": "tanto faz", "session_id": sid})
    data = r3.json()
    assert sorted(p["id"] for p in data["products"]) == [3001, 3002, 3003, 3004]


def test_chat_endpoint_chuteira_nike(client, db_session):
    """Regression: 'chuteira nike' must find products with 'chuteira' in the
    name even when breadcrumbs are empty and no 'futebol' text exists."""
    category = Category(id=93, slug="chuteiras-para-campo", url="/c/93-chuteiras-para-campo", name="Chuteiras Para Campo")
    db_session.add(category)
    product = Product(
        id=2001,
        slug="chuteira-nike-vapor-campo",
        url="https://www.tivolli.com.br/2001-chuteira-nike-vapor-campo",
        name="Chuteira Nike Vapor Club Campo",
        currency="BRL",
        price=Decimal("399.90"),
        sizes=["38", "39", "40"],
        available=True,
        images=["https://example.com/img.jpg"],
        category_id=93,
        breadcrumbs=[],
        brand="Nike",
        status=ProductStatus.ACTIVE,
        scraped_at=datetime.now(UTC),
    )
    db_session.add(product)
    db_session.commit()

    sid = "chuteira-flow"
    # Calçado sem preferências: o bot pergunta o gênero primeiro
    r1 = client.post("/api/chat", json={"message": "chuteira nike", "session_id": sid})
    assert r1.status_code == 200
    assert r1.json()["products"] == []

    r2 = client.post("/api/chat", json={"message": "tanto faz", "session_id": sid})
    assert "número" in r2.json()["reply"].lower()

    r3 = client.post("/api/chat", json={"message": "tanto faz", "session_id": sid})
    data = r3.json()
    assert len(data["products"]) >= 1
    assert any("chuteira" in p["name"].lower() for p in data["products"])
    matched = [p for p in data["products"] if p["id"] == 2001][0]
    assert matched["available"] is True
    assert matched["status"] == "active"


def test_chat_endpoint_stock_flag_roundtrip(client, db_session):
    """The API must preserve available/status so the UI shows correct stock."""
    _seed_products(db_session, count=6)
    response = client.post("/api/chat", json={"message": "produtos"})
    assert response.status_code == 200
    products = response.json()["products"]
    assert len(products) > 0
    for p in products:
        assert isinstance(p["available"], bool)
        assert p["status"] in ("active", "out_of_stock", "disappeared")
        if p["available"]:
            assert p["status"] == "active"

