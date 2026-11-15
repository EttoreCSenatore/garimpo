"""Live smoke check of the scraper against the real store (about 4 requests).

Run by the weekly ``Scraper canary`` workflow, or by hand: ``python -m app.canary``.
It fails (exit code 1) when the store's markup changed enough to break parsing, so
a redesign is noticed within days instead of after a silent empty scrape.
"""
from __future__ import annotations

import asyncio
import sys

from app.scraper.categories import fetch_categories
from app.scraper.client import RateLimitedClient
from app.scraper.listings import extract_product_urls
from app.scraper.products import parse_product

MIN_CATEGORIES = 10


async def run() -> list[str]:
    problems: list[str] = []
    client = RateLimitedClient()
    try:
        categories = await fetch_categories(client)
        if len(categories) < MIN_CATEGORIES:
            problems.append(f"only {len(categories)} categories found (expected >= {MIN_CATEGORIES})")
            return problems

        urls: list[str] = []
        category = None
        for category in categories[:3]:
            resp = await client.get(f"/{category.slug}")
            urls = extract_product_urls(resp.text)
            if urls:
                break
        if not urls:
            problems.append("no product links found on the first category pages")
            return problems

        resp = await client.get(urls[0])
        product = parse_product(resp.text, urls[0], category.id if category else None)
        if not product["name"] or product["name"] == "Unknown Product":
            problems.append(f"{urls[0]}: no product name")
        if product["price"] is None:
            problems.append(f"{urls[0]}: no price")
        if not product["images"]:
            problems.append(f"{urls[0]}: no images")
        if not product["sizes"] and product["available"]:
            problems.append(f"{urls[0]}: available but no sizes")
    finally:
        await client.close()
    return problems


def main() -> int:
    problems = asyncio.run(run())
    if problems:
        print("Scraper canary FAILED:")
        for p in problems:
            print(f" - {p}")
        return 1
    print("Scraper canary OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
