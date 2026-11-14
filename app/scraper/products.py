from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import structlog
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.models import Installments, ProductStatus
from app.scraper.client import RateLimitedClient
from app.security import safe_http_url

logger = structlog.get_logger()

PRODUCT_URL_RE = re.compile(r"(?:^|/)(\d+)-([\w-]+)")
PRICE_RE = re.compile(r"R\$\s*([\d.]+,\d{2})")
CODE_RE = re.compile(r"(?:[A-Z]{2}\d{4}\s*\d{3}|[A-Z]{2,4}\d{4,6})")


def _parse_price(text: str) -> Decimal | None:
    match = PRICE_RE.search(text)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _extract_text(node) -> str:
    if node is None:
        return ""
    return node.text(strip=True) or ""


def parse_product(html: str, url: str, category_id: int | None = None) -> dict:
    tree = HTMLParser(html)
    result: dict = {}

    match = PRODUCT_URL_RE.search(url)
    if match:
        result["id"] = int(match.group(1))
        result["slug"] = match.group(2)
    else:
        raise ValueError(f"Cannot extract product id from url: {url}")

    result["url"] = url

    name_node = tree.css_first("h1")
    result["name"] = _extract_text(name_node) if name_node else "Unknown Product"

    codigo = None
    code_node = tree.css_first(".sku, .codigo, [class*='codigo'], [class*='sku']")
    if code_node:
        codigo = _extract_text(code_node)
    if not codigo:
        m = CODE_RE.search(html)
        if m:
            codigo = m.group(0)
    result["codigo"] = codigo

    result["currency"] = "BRL"

    price = None
    price_selectors = [
        ".preco", ".price", "[class*='preco']", "[class*='price']",
        "strong[class*='por']", "[class*='por-preco']",
    ]
    for sel in price_selectors:
        node = tree.css_first(sel)
        if node:
            text = _extract_text(node)
            price = _parse_price(text)
            if price:
                break
    if not price:
        por_m = re.search(r"Por:\s*R\$\s*([\d.]+,\d{2})", html)
        if por_m:
            raw = por_m.group(1).replace(".", "").replace(",", ".")
            try:
                price = Decimal(raw)
            except InvalidOperation:
                price = None
    result["price"] = price

    price_boleto = None
    boleto_m = re.search(
        r"(?:boleto|transferência)[^R$]*R\$\s*([\d.]+,\d{2})", html, re.IGNORECASE
    )
    if boleto_m:
        raw = boleto_m.group(1).replace(".", "").replace(",", ".")
        try:
            price_boleto = Decimal(raw)
        except InvalidOperation:
            price_boleto = None
    result["price_boleto"] = price_boleto

    installments = None
    inst_m = re.search(
        r"em\s+(\d+)x[^R$]*R\$\s*([\d.]+,\d{2})",
        html,
        re.IGNORECASE,
    )
    if inst_m:
        count = int(inst_m.group(1))
        val_raw = inst_m.group(2).replace(".", "").replace(",", ".")
        try:
            value = Decimal(val_raw)
            after = html[inst_m.end():inst_m.end() + 60]
            interest_free = "sem juros" in after.lower()
            installments = Installments(
                count=count, value=value, interest_free=interest_free
            )
        except InvalidOperation:
            installments = None
    result["installments"] = installments.model_dump() if installments else None

    sizes: list[str] = []
    size_selectors = [
        ".product-options li a", ".product-options a", ".product-options li",
        "button.tamanho", "button.size",
        "button[class*='tamanho']", "button[class*='size']",
        "a.tamanho", "a.size",
        "a[class*='tamanho']", "a[class*='size']",
        "span.tamanho", "span.size",
        "li.tamanho", "li.size",
    ]
    seen_sizes: set[str] = set()
    has_size_options = False
    has_available_size = False

    for sel in size_selectors:
        nodes = tree.css(sel)
        if nodes:
            has_size_options = True
            for node in nodes:
                text = _extract_text(node)
                if text and len(text) <= 10 and text not in seen_sizes:
                    sizes.append(text)
                    seen_sizes.add(text)
                    classes = node.attributes.get("class", "").lower()
                    if not any(dis in classes for dis in ["unavailable", "indisponivel", "out", "disabled"]):
                        has_available_size = True

    if has_size_options:
        available = has_available_size
    else:
        buy_btn = tree.css_first("input[value*='Comprar'], button[value*='Comprar'], .comprar, form[action*='carrinho']")
        out_indicator = tree.css_first(".indisponivel, .esgotado, [class*='esgotado'], [class*='indisponivel']")
        available = bool(buy_btn and not out_indicator)

    result["sizes"] = sizes
    result["available"] = available

    description = ""
    desc_selectors = [
        ".descricao", ".description", "[class*='descricao']",
        "[class*='description']", "#descricao", "#informacoes",
    ]
    for sel in desc_selectors:
        node = tree.css_first(sel)
        if node:
            description = _extract_text(node)
            if description:
                break
    if not description:
        info_m = re.search(
            r"Informações?\s+do\s+Produto[^<]*<[^>]*>(.*?)</",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if info_m:
            description = re.sub(r"<[^>]+>", " ", info_m.group(1)).strip()
    result["description"] = description

    images: list[str] = []
    for node in tree.css("img[src]"):
        src = node.attributes.get("src", "")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if any(k in src.lower() for k in ["produto", "product", "catalog"]):
            images.append(src)
    if not images:
        for node in tree.css("img"):
            src = node.attributes.get("src") or node.attributes.get("data-src") or ""
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                if src.startswith("http"):
                    images.append(src)
    # Keep only plain http(s) image URLs (drops javascript:/data: and IP literals).
    result["images"] = [u for u in dict.fromkeys(images) if safe_http_url(u)]

    result["category_id"] = category_id

    breadcrumbs: list[str] = []
    crumb_selectors = [".breadcrumb", "nav[aria-label*='breadcrumb']", "[class*='breadcrumb']"]
    for sel in crumb_selectors:
        node = tree.css_first(sel)
        if node:
            for a in node.css("a, span, li"):
                text = _extract_text(a)
                if text:
                    breadcrumbs.append(text)
            break
    result["breadcrumbs"] = breadcrumbs

    result["scraped_at"] = datetime.now(UTC)
    result["status"] = ProductStatus.ACTIVE if available else ProductStatus.OUT_OF_STOCK

    return result


async def fetch_and_parse_product(
    client: RateLimitedClient,
    url: str,
    category_id: int | None = None,
) -> dict | None:
    try:
        resp = await client.get_raw(url)
        if resp.status_code == 404:
            return {
                "id": _extract_id(url),
                "status": ProductStatus.DISAPPEARED,
                "url": url,
            }
        resp.raise_for_status()
        return parse_product(resp.text, url, category_id)
    except Exception as exc:
        logger.error("scraper.parse_error", url=url, error=str(exc))
        from app.splunk_hec import get_hec_logger
        await get_hec_logger().send(
            {
                "event_type": "tivolli.error.parse",
                "url": url,
                "error": str(exc),
            }
        )
        return None


def _extract_id(url: str) -> int | None:
    match = PRODUCT_URL_RE.search(url)
    if match:
        return int(match.group(1))
    return None


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
