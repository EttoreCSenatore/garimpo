from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.config import settings
from app.scraper.client import RateLimitedClient

logger = structlog.get_logger()

PRODUCT_URL_RE = re.compile(r"(?:^|/)(\d+)-([\w-]+)")
MAX_PAGES = 200


def extract_product_urls(html: str) -> list[str]:
    tree = HTMLParser(html)
    urls: list[str] = []
    seen: set[str] = set()

    for node in tree.css("a[href]"):
        href = node.attributes.get("href", "")
        if not href:
            continue
        if "/c/" in href:
            continue
        if PRODUCT_URL_RE.search(href):
            full = urljoin(settings.base_url, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
    return urls


def is_page_empty(html: str) -> bool:
    tree = HTMLParser(html)
    for node in tree.css("a[href]"):
        href = node.attributes.get("href", "")
        if "/c/" in href:
            continue
        if PRODUCT_URL_RE.search(href):
            return False
    return True


async def crawl_category(
    category_id: int,
    category_slug: str,
    client: RateLimitedClient,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    all_urls: list[str] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        path = f"/c/{category_id}-{category_slug}?p={page}"
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
