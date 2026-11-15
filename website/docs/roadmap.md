---
sidebar_position: 11
title: Roadmap
---

# Roadmap and review notes

A code review of the original import led to the security and reliability fixes already merged.
These are the remaining ideas, roughly by value.

## Correctness

- **Detect disappeared products from crawls**: today a product is marked `disappeared` only on a 404. Compare each full crawl against the catalog and mark missing products after N consecutive misses.
- **Parser resilience**: parse prices from structured data (JSON-LD / meta tags) before CSS selectors and regexes, and alert when the parse failure rate spikes.
- **Smarter relevance**: rank chat results by a text score (name match) before popularity, and add synonyms learned from the catalog.

## Performance and scale

- **Async database access**: the SQLite calls run synchronously inside async handlers; move heavy queries to a thread pool or adopt an async driver.
- **PostgreSQL option**: documented migration path and Alembic migrations (currently `create_all` plus idempotent indexes).
- **Shared rate limiting**: move limits and chat sessions to Redis if more than one instance is needed.

## Product

- **Price-drop alerts** using the history table.
- **Category-aware UI**: filters and sorting next to the chat.
- **Real product images in demos** once permission is granted.

## Operations

- **Metrics**: Prometheus endpoint (scrape duration, parse failures, queue depth).
- **Pin and lock Python dependencies** (`pip-compile`) for fully reproducible images.
- **Release automation**: tagged releases with a published container image and SBOM.
