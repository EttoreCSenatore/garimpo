from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path

import pytest

from app.scraper.client import RateLimitedClient
from app.scraper.listings import extract_product_urls, is_page_empty
from app.scraper.products import PRODUCT_URL_RE, infer_brand, parse_product

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_product_parser_nike_airmax():
    html = read_fixture("product_nike_airmax.html")
    url = "https://www.tivolli.com.br/12345-tenis-nike-air-max-90"
    result = parse_product(html, url, category_id=11)

    assert result["id"] == 12345
    assert result["slug"] == "tenis-nike-air-max-90"
    assert result["url"] == url
    assert result["name"] == "Tênis Nike Air Max 90"
    assert result["codigo"] == "FB7689 003"
    assert result["currency"] == "BRL"
    assert result["price"] == Decimal("899.90")
    assert result["price_boleto"] == Decimal("809.91")
    assert result["installments"] is not None
    assert result["installments"]["count"] == 10
    assert result["installments"]["value"] == Decimal("89.99")
    assert result["installments"]["interest_free"] is True
    assert "38" in result["sizes"]
    assert "40" in result["sizes"]
    assert result["available"] is True
    assert "Nike Air Max 90" in result["description"]
    assert len(result["images"]) == 3
    assert result["category_id"] == 11
    assert "Calçados" in result["breadcrumbs"]
    assert "Tênis" in result["breadcrumbs"]
    assert result["status"] == "active"


def test_product_parser_adidas_trefoil():
    html = read_fixture("product_adidas_trefoil.html")
    url = "https://www.tivolli.com.br/67890-camisa-adidas-originals-trefoil"
    result = parse_product(html, url, category_id=21)

    assert result["id"] == 67890
    assert result["name"] == "Camisa Adidas Originals Trefoil"
    assert result["codigo"] == "GN3486"
    assert result["price"] == Decimal("249.90")
    assert result["price_boleto"] == Decimal("224.91")
    assert result["installments"]["count"] == 6
    assert "P" in result["sizes"]
    assert result["available"] is True
    assert result["category_id"] == 21


def test_product_parser_puma_future_out_of_stock():
    html = read_fixture("product_puma_future.html")
    url = "https://www.tivolli.com.br/11111-chuteira-puma-future-7-ultimate"
    result = parse_product(html, url, category_id=31)

    assert result["id"] == 11111
    assert result["name"] == "Chuteira Puma Future 7 Ultimate"
    assert result["price"] == Decimal("1299.90")
    assert result["available"] is False
    assert result["status"] == "out_of_stock"


def test_infer_brand():
    assert infer_brand("Tênis Nike Air Max", "FB7689 003") == "Nike"
    assert infer_brand("Camisa Adidas Originals", "GN3486") == "Adidas"
    assert infer_brand("Chuteira Puma Future", "107707 01") == "Puma"
    assert infer_brand("Produto Genérico", None) is None


def test_listing_extract_product_urls():
    html = """
    <html><body>
    <a href="/12345-tenis-nike">Nike</a>
    <a href="/67890-camisa-adidas">Adidas</a>
    <a href="/c/10-calcados">Categoria</a>
    <a href="https://www.tivolli.com.br/11111-chuteira-puma">Puma</a>
    </body></html>
    """
    urls = extract_product_urls(html)
    assert len(urls) == 3
    assert any("12345" in u for u in urls)
    assert any("67890" in u for u in urls)
    assert any("11111" in u for u in urls)


def test_listing_empty_page():
    html = "<html><body><p>No products here</p></body></html>"
    assert is_page_empty(html) is True

    html_with_product = '<html><body><a href="/12345-tenis">Product</a></body></html>'
    assert is_page_empty(html_with_product) is False


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


def test_product_url_regex():
    m = PRODUCT_URL_RE.search("/12345-tenis-nike-air-max")
    assert m is not None
    assert m.group(1) == "12345"
    assert m.group(2) == "tenis-nike-air-max"
