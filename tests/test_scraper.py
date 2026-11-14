from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path

import pytest

from app.scraper.client import RateLimitedClient
from app.scraper.listings import extract_product_urls, is_page_empty
from app.scraper.products import infer_brand, parse_product, parse_product_url

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_product_parser_configurable_shoe():
    html = read_fixture("product_chuteira_demo.html")
    url = "https://www.tivolli.com.br/chuteira-demo-pro-fg-9001"
    result = parse_product(html, url, category_id=7)

    assert result["id"] == 9001
    assert result["slug"] == "chuteira-demo-pro-fg"
    assert result["name"] == "Chuteira Demo Pro FG"
    assert result["codigo"] == "TIV9001"
    assert result["brand"] == "Marca Demo"
    # The lowest price among the sizes on offer wins over the JSON-LD teaser price.
    assert result["price"] == Decimal("1899.90")
    assert result["price_boleto"] == Decimal("1804.91")  # -5% cash discount
    assert result["installments"] == {"count": 6, "value": 316.65, "interest_free": True}
    assert result["sizes"] == ["39", "40", "41"]
    assert result["available"] is True
    assert result["status"] == "active"
    assert result["description"] == "Descrição de demonstração."
    assert len(result["images"]) == 3
    assert all("/f/" in u for u in result["images"])  # full-size gallery images
    assert result["breadcrumbs"] == ["Esportes", "Futebol"]
    assert result["category_id"] == 7


def test_product_parser_without_cash_discount_or_description():
    html = read_fixture("product_camisa_demo.html")
    result = parse_product(html, "https://www.tivolli.com.br/camisa-demo-treino-9002")

    assert result["price"] == Decimal("149.90")
    assert result["sizes"] == ["P", "M"]
    assert result["brand"] == "Outra Marca"
    assert result["installments"]["count"] == 3
    assert result["description"] == ""
    assert len(result["images"]) == 1


def test_product_parser_out_of_stock():
    html = read_fixture("product_esgotado_demo.html")
    result = parse_product(html, "https://www.tivolli.com.br/tenis-demo-esgotado-9003")

    assert result["price"] == Decimal("599.90")
    assert result["price_boleto"] is None
    assert result["sizes"] == []
    assert result["available"] is False
    assert result["status"] == "out_of_stock"


def test_product_parser_rejects_non_product_url():
    with pytest.raises(ValueError):
        parse_product("<html></html>", "https://www.tivolli.com.br/homens/chuteiras")


def test_infer_brand():
    assert infer_brand("Tênis Nike Air Max", "FB7689 003") == "Nike"
    assert infer_brand("Camisa Adidas Originals", "GN3486") == "Adidas"
    assert infer_brand("Chuteira Puma Future", "107707 01") == "Puma"
    assert infer_brand("Produto Genérico", None) is None


def test_listing_extract_product_urls():
    urls = extract_product_urls(read_fixture("listing_demo.html"))
    assert urls == [
        "https://www.tivolli.com.br/chuteira-demo-pro-fg-9001",
        "https://www.tivolli.com.br/camisa-demo-treino-9002",
    ]


def test_listing_empty_page():
    assert is_page_empty("<html><body><p>No products here</p></body></html>") is True
    assert is_page_empty(read_fixture("listing_demo.html")) is False


@pytest.mark.asyncio
async def test_category_discovery_from_google_sitemap(monkeypatch):
    from types import SimpleNamespace

    from app.scraper import categories as cats

    class FakeClient:
        async def get_raw(self, url):
            assert url.endswith("/google_sitemap.xml")
            return SimpleNamespace(content=read_fixture("google_sitemap_demo.xml").encode(), raise_for_status=lambda: None)

    found = await cats.fetch_categories(FakeClient())
    slugs = [c.slug for c in found]
    assert set(slugs) == {"homens", "homens/chuteiras", "esportes/futebol", "cat-outlet"}
    assert slugs.index("homens/chuteiras") < slugs.index("homens")
    assert all(c.id == cats.category_id_for(c.slug) for c in found)


@pytest.mark.asyncio
async def test_client_blocks_robots_disallowed_params_and_paths():
    from app.scraper.client import DisallowedRequestError

    c = RateLimitedClient(jitter_min_ms=0, jitter_max_ms=0, requests_per_second=1000)
    for target in ["/homens/chuteiras?product_list_order=price", "/catalogsearch/result/?q=a", "/checkout/cart"]:
        with pytest.raises(DisallowedRequestError):
            await c.get_raw(target)
    await c.close()


@pytest.mark.asyncio
async def test_rate_limit_jitter():
    client = RateLimitedClient(
        requests_per_second=10,
        jitter_min_ms=50,
        jitter_max_ms=100,
        max_retries=0,
    )

    start = time.monotonic()
    for _ in range(3):
        await client._throttle()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.15
    assert elapsed < 2.0

    await client.close()


@pytest.mark.asyncio
async def test_rate_limit_min_interval():
    client = RateLimitedClient(
        requests_per_second=2,
        jitter_min_ms=0,
        jitter_max_ms=0,
        max_retries=0,
    )

    start = time.monotonic()
    for _ in range(3):
        await client._throttle()
    elapsed = time.monotonic() - start

    assert elapsed >= 1.0

    await client.close()


def test_product_url_parsing():
    assert parse_product_url("https://www.tivolli.com.br/tenis-nike-air-max-12345") == (12345, "tenis-nike-air-max")
    assert parse_product_url("https://www.tivolli.com.br/homens/chuteiras") is None
    assert parse_product_url("https://www.tivolli.com.br/mulheres") is None
