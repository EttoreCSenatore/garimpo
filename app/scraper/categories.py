from __future__ import annotations

import re
import zlib
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import structlog
from lxml import etree

from app.config import settings
from app.db import session_scope
from app.models import Category
from app.scraper.client import RateLimitedClient
from app.scraper.listings import _same_site_url

logger = structlog.get_logger()

# Category pages in the sitemap: the store's department roots and everything below them.
# CMS pages (sobre-nos, marcas, politicas...) and the home page are not categories.
CATEGORY_ROOTS = {"homens", "mulheres", "infantil", "esportes", "roupas", "tenis"}
CATEGORY_PATH_RE = re.compile(r"^/((?:cat-[a-z0-9-]+)|(?:[a-z0-9-]+(?:/[a-z0-9-]+)*))/?$")


def category_id_for(path: str) -> int:
    """Stable positive id for a category path (the new store exposes no numeric category id)."""
    return zlib.crc32(path.strip("/").encode()) & 0x7FFFFFFF


def category_path(url: str) -> str | None:
    path = urlparse(url).path
    match = CATEGORY_PATH_RE.match(path)
    if not match:
        return None
    path = match.group(1)
    if path.split("/")[0] not in CATEGORY_ROOTS and not path.startswith("cat-"):
        return None
    return path


async def fetch_categories(client: RateLimitedClient) -> list[Category]:
    sitemap_url = urljoin(settings.base_url, "/google_sitemap.xml")
    resp = await client.get_raw(sitemap_url)
    resp.raise_for_status()

    # Hardened parser: the sitemap is untrusted input (no entities, DTDs or network access).
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
    root = etree.fromstring(resp.content, parser=parser)
    namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls = root.xpath("//sm:url/sm:loc/text()", namespaces=namespaces)
    if not urls:
        urls = root.xpath("//loc/text()")

    categories: list[Category] = []
    seen_ids: set[int] = set()

    for url in urls:
        url = _same_site_url(str(url))
        path = category_path(url) if url else None
        if not path:
            continue
        cat_id = category_id_for(path)
        if cat_id in seen_ids:
            continue
        seen_ids.add(cat_id)
        categories.append(
            Category(
                id=cat_id,
                slug=path,
                url=url,
                name=path.rsplit("/", 1)[-1].removeprefix("cat-").replace("-", " ").title(),
            )
        )

    # Most specific categories first, so a product is filed under its leaf category.
    categories.sort(key=lambda c: -c.slug.count("/"))

    logger.info("scraper.categories.fetched", count=len(categories))
    return categories


def store_categories(categories: list[Category]) -> None:
    with session_scope() as session:
        for cat in categories:
            existing = session.get(Category, cat.id)
            if existing:
                existing.slug = cat.slug
                existing.url = cat.url
                existing.name = cat.name
                existing.last_seen = datetime.now(UTC)
            else:
                session.add(cat)
        session.commit()


async def discover_categories(client: RateLimitedClient | None = None) -> list[Category]:
    own_client = client is None
    if own_client:
        client = RateLimitedClient()
    try:
        categories = await fetch_categories(client)
        store_categories(categories)
        return categories
    finally:
        if own_client and client:
            await client.close()
