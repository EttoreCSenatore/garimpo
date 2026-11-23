from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlparse

import structlog
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.events import emit
from app.failures import record_parse_failure
from app.models import Installments, ProductStatus
from app.scraper.client import RateLimitedClient
from app.security import safe_http_url

logger = structlog.get_logger()

# Product pages live at /{slug}-{id} (Magento): a single path segment ending in the numeric id.
PRODUCT_URL_RE = re.compile(r"^/([a-z0-9][a-z0-9-]*?)-(\d+)/?$")
PRICE_RE = re.compile(r"R\$\s*([\d.]+,\d{2})")
PERCENT_RE = re.compile(r"-\s*(\d{1,2})\s*%")
CENT = Decimal("0.01")


def parse_product_url(url: str) -> tuple[int, str] | None:
    """Return (id, slug) for a product URL, or None when the path is not a product page."""
    m = PRODUCT_URL_RE.match(urlparse(url).path)
    return (int(m.group(2)), m.group(1)) if m else None


def _money(value) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_price(text: str) -> Decimal | None:
    match = PRICE_RE.search(text)
    if not match:
        return None
    return _money(match.group(1).replace(".", "").replace(",", "."))


def _extract_text(node) -> str:
    if node is None:
        return ""
    return node.text(strip=True) or ""


def _json_ld(tree, type_name: str):
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == type_name:
                return item
    return None


def _magento_init(tree):
    """Yield every parsed ``text/x-magento-init`` JSON blob (the page's embedded config)."""
    for node in tree.css('script[type="text/x-magento-init"]'):
        try:
            yield json.loads(node.text())
        except ValueError:
            continue


def _find_gallery(tree) -> list[dict]:
    def walk(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            if obj and isinstance(obj[0], dict) and "full" in obj[0]:
                return obj
            for value in obj:
                found = walk(value)
                if found:
                    return found
        return None

    for blob in _magento_init(tree):
        found = walk(blob)
        if found:
            return found
    return []


def _find_options_config(tree) -> dict | None:
    def walk(obj):
        if isinstance(obj, dict):
            if "optionPrices" in obj and isinstance(obj.get("attributes"), dict):
                return obj
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = walk(value)
                if found:
                    return found
        return None

    for blob in _magento_init(tree):
        found = walk(blob)
        if found:
            return found
    return None


def _sizes_and_price(config: dict | None) -> tuple[list[str], Decimal | None]:
    """Sizes still offered (Magento only lists options that can be bought) and their lowest price."""
    if not config:
        return [], None
    attributes = [a for a in config["attributes"].values() if str(a.get("code", "")).startswith("tamanho")]
    # Prefer the shoe-number attribute; fall back to a generic size (P/M/G, "Único").
    attributes.sort(key=lambda a: a.get("code") != "tamanho_calcado")
    for attr in attributes:
        options = attr.get("options") or []
        if not options:
            continue
        sizes = [str(o["label"]) for o in options if o.get("label")]
        prices = [
            _money(config["optionPrices"][pid]["finalPrice"]["amount"])
            for o in options
            for pid in o.get("products", [])
            if pid in config.get("optionPrices", {})
        ]
        prices = [p for p in prices if p is not None]
        return sizes, (min(prices) if prices else None)
    return [], None


def parse_product(html: str, url: str, category_id: int | None = None) -> dict:
    tree = HTMLParser(html)
    parsed = parse_product_url(url)
    if not parsed:
        raise ValueError(f"Cannot extract product id from url: {url}")
    result: dict = {"id": parsed[0], "slug": parsed[1], "url": url, "currency": "BRL"}

    ld = _json_ld(tree, "Product") or {}
    offer = ld.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}

    name_node = tree.css_first("h1")
    result["name"] = _extract_text(name_node) or ld.get("name") or "Unknown Product"
    result["codigo"] = (
        (str(ld["sku"])[:64] if ld.get("sku") else None)
        or _extract_text(tree.css_first(".product.attribute.sku .value"))
        or None
    )

    brand = ld.get("brand")
    result["brand"] = (brand.get("name") if isinstance(brand, dict) else brand) or None

    sizes, size_price = _sizes_and_price(_find_options_config(tree))
    result["sizes"] = sizes

    price = size_price or _money(offer.get("price"))
    if price is None:
        node = tree.css_first("[data-price-amount]")
        price = _money(node.attributes.get("data-price-amount")) if node else None
    result["price"] = price

    # Cash-payment discount ("R$ x à vista (-5%)"); recomputed from the price we actually keep.
    price_boleto = None
    pct = tree.css_first(".promocao-preco-avista .percent-desconto")
    pct_m = PERCENT_RE.search(_extract_text(pct)) if pct else None
    if price is not None and pct_m:
        price_boleto = (price * (Decimal(100) - Decimal(pct_m.group(1))) / Decimal(100)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
    result["price_boleto"] = price_boleto

    installments = None
    count_node = tree.css_first(".parcela .num-parcela")
    count_m = re.search(r"(\d+)", _extract_text(count_node)) if count_node else None
    if price is not None and count_m and int(count_m.group(1)) > 1:
        count = int(count_m.group(1))
        value = (price / count).quantize(CENT, rounding=ROUND_HALF_UP)
        installments = Installments(
            count=count,
            value=value,
            interest_free="sem juros" in _extract_text(tree.css_first(".parcela")).lower(),
        )
    # Stored in a JSON column, which cannot hold Decimal: keep the value as a plain number.
    result["installments"] = (
        {"count": installments.count, "value": float(installments.value), "interest_free": installments.interest_free}
        if installments
        else None
    )

    out_of_stock = tree.css_first(".stock.unavailable") is not None
    in_stock_schema = "instock" in str(offer.get("availability", "")).lower()
    result["available"] = (bool(sizes) or in_stock_schema) and not out_of_stock

    description = ld.get("description") or ""
    if not description:
        description = _extract_text(tree.css_first(".product.attribute.description .value"))
    result["description"] = re.sub(r"\s+", " ", description).strip()

    images: list[str] = []
    for item in _find_gallery(tree):
        if item.get("type", "image") == "image":
            images.append(item.get("full") or item.get("img") or "")
    if not images and ld.get("image"):
        images.append(ld["image"] if isinstance(ld["image"], str) else ld["image"][0])
    # Keep only plain http(s) image URLs on safe hosts (drops javascript:/data: and IP literals).
    result["images"] = [u for u in dict.fromkeys(images) if u and safe_http_url(u)]

    result["category_id"] = category_id

    crumbs = _json_ld(tree, "BreadcrumbList") or {}
    names = [
        (e.get("item") or {}).get("name", "")
        for e in sorted(crumbs.get("itemListElement", []), key=lambda e: e.get("position", 0))
    ]
    # Drop "Início" (home) and the last entry, which is the product itself.
    result["breadcrumbs"] = [n for n in names[1:-1] if n]

    result["scraped_at"] = datetime.now(UTC)
    result["status"] = ProductStatus.ACTIVE if result["available"] else ProductStatus.OUT_OF_STOCK
    return result


async def fetch_and_parse_product(
    client: RateLimitedClient,
    url: str,
    category_id: int | None = None,
) -> dict | None:
    html: str | None = None
    status: int | None = None
    try:
        resp = await client.get_raw(url)
        status = resp.status_code
        if resp.status_code == 404:
            return {
                "id": _extract_id(url),
                "status": ProductStatus.DISAPPEARED,
                "url": url,
            }
        resp.raise_for_status()
        html = resp.text
        result = parse_product(html, url, category_id)
        if result["name"] == "Unknown Product":
            raise ValueError("page has no product data (markup changed?)")
        return result
    except Exception as exc:
        logger.error("scraper.parse_error", url=url, error=str(exc))
        emit(
            {
                "event_type": "garimpo.error.parse",
                "url": url,
                "error": str(exc),
            }
        )
        record_parse_failure(url, f"{type(exc).__name__}: {exc}", http_status=status, html=html)
        return None


def _extract_id(url: str) -> int | None:
    parsed = parse_product_url(url)
    return parsed[0] if parsed else None


def infer_brand(name: str, codigo: str | None) -> str | None:
    brand_map = {
        "nike": "Nike",
        "adidas": "Adidas",
        "puma": "Puma",
        "reebok": "Reebok",
        "mizuno": "Mizuno",
        "asics": "Asics",
        "new balance": "New Balance",
        "olympikus": "Olympikus",
        "under armour": "Under Armour",
        "fila": "Fila",
        "umbro": "Umbro",
        "topper": "Topper",
        "penalty": "Penalty",
        "kappa": "Kappa",
        "joma": "Joma",
        "yonex": "Yonex",
        "volkl": "Volkl",
        "hoka": "Hoka",
        "wilson": "Wilson",
        "head": "Head",
        "babolat": "Babolat",
        "dunlop": "Dunlop",
        "osklen": "Osklen",
    }
    text = (name + " " + (codigo or "")).lower()
    for key, brand in brand_map.items():
        # Word boundaries so "head" does not match "ahead" or "fila" "filame".
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text):
            return brand
    return None
