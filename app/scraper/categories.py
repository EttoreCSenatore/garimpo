from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import structlog
from lxml import etree
from sqlmodel import Session, select

from app.config import settings
from app.db import session_scope
from app.models import Category
from app.scraper.client import RateLimitedClient

logger = structlog.get_logger()

CATEGORY_URL_RE = re.compile(r"/c/(\d+)-([\w-]+)")


async def fetch_categories(client: RateLimitedClient) -> list[Category]:
    sitemap_url = urljoin(settings.base_url, "/sitemap.xml")
    resp = await client.get_raw(sitemap_url)
    resp.raise_for_status()

    root = etree.fromstring(resp.content)
    namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls = root.xpath("//sm:url/sm:loc/text()", namespaces=namespaces)
    if not urls:
        urls = root.xpath("//loc/text()")

    categories: list[Category] = []
    seen_ids: set[int] = set()

    for url in urls:
        match = CATEGORY_URL_RE.search(url)
        if not match:
            continue
        cat_id = int(match.group(1))
        if cat_id in seen_ids:
            continue
        seen_ids.add(cat_id)
        slug = match.group(2)
        categories.append(
            Category(
                id=cat_id,
                slug=slug,
                url=url,
                name=slug.replace("-", " ").title(),
            )
        )

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
                existing.last_seen = datetime.now(timezone.utc)
            else:
                session.add(cat)
        session.commit()


async def discover_categories(client: Optional[RateLimitedClient] = None) -> list[Category]:
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
