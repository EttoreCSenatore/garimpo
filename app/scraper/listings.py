from __future__ import annotations

from urllib.parse import urljoin, urlparse

import structlog
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.config import settings
from app.scraper.client import RateLimitedClient
from app.scraper.products import parse_product_url
from app.security import safe_http_url

logger = structlog.get_logger()

MAX_PAGES = 200


def _same_site_url(url: str) -> str | None:
    """Accept only http(s) URLs on the configured shop host (rejects javascript:, data:, other hosts)."""
    host = (urlparse(settings.base_url).hostname or "").lower().removeprefix("www.")
    return safe_http_url(url, [host])


def extract_product_urls(html: str) -> list[str]:
    """Product links of a Magento listing page (``a.product-item-link``), in page order."""
    tree = HTMLParser(html)
    urls: list[str] = []
    seen: set[str] = set()
    for node in tree.css("a.product-item-link[href]"):
        href = node.attributes.get("href", "")
        full = _same_site_url(urljoin(settings.base_url, href))
        if full and parse_product_url(full) and full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def is_page_empty(html: str) -> bool:
    return not extract_product_urls(html)


async def crawl_category(
    category_id: int,
    category_slug: str,
    client: RateLimitedClient,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    all_urls: list[str] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        path = f"/{category_slug}?p={page}"
        try:
            resp = await client.get(path)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
        except Exception as exc:
            logger.error("scraper.listing.error", category_id=category_id, page=page, error=str(exc))
            break

        if is_page_empty(resp.text):
            break

        urls = extract_product_urls(resp.text)
        if not urls:
            break

        new_count = 0
        for u in urls:
            if u not in seen:
                seen.add(u)
                all_urls.append(u)
                new_count += 1

        if new_count == 0:
            break

    logger.info(
        "scraper.listing.crawled",
        category_id=category_id,
        pages=page,
        products=len(all_urls),
    )
    return all_urls
