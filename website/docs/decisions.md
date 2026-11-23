---
sidebar_position: 13
title: Decision log
---

# Decision log

Each row is a decision with its date and reason. When a decision changes, the old row is marked superseded and a new row is added, so the history stays.

| # | Date | Decision | Reason | Status |
| --- | --- | --- | --- | --- |
| 001 | 2026-11-14 | Python, FastAPI and SQLModel for the API and scraper | One language for scraping, API and tests; automatic OpenAPI docs | Accepted |
| 002 | 2026-11-14 | SQLite (WAL) as the database | Zero setup, one file to back up, enough for a single catalog; Postgres stays on the roadmap | Accepted |
| 003 | 2026-11-14 | Rule-based chat, no LLM | Every answer is computed from the database, with no API key, cost or hallucinated prices | Accepted (an optional AI mode is under study, M7) |
| 004 | 2026-11-14 | One process-wide request budget (about 1 req/s with jitter) | Parallel jobs must never multiply the load on the store | Accepted |
| 005 | 2026-11-14 | Mirror robots.txt in code (paths and query parameters) | Blocked URLs fail before any request is made | Accepted |
| 006 | 2026-11-14 | Image proxy with an exact host allow-list, no IPs, size cap, revalidated redirects | Prevents SSRF through the proxy | Accepted |
| 007 | 2026-11-14 | Rename the project to Garimpo; the store is only the data source | The project must not carry the store's name | Accepted |
| 008 | 2026-11-14 | Parse the store's Magento pages from JSON-LD and the page's embedded config, not CSS selectors | Structured data survives redesigns better than markup and regexes | Accepted |
| 009 | 2026-11-14 | Full-text index (FTS5) on name, brand, breadcrumbs and slug only; descriptions excluded | Descriptions caused false matches | Accepted |
| 010 | 2026-11-14 | Record price history only when a tracked field changes | Small table, every row is a real change | Accepted |
| 011 | 2026-11-14 | Public repository under the MIT license; `main` only through pull requests with required checks | Open by default, nothing reaches `main` unreviewed or red | Accepted |
| 012 | 2026-11-14 | Documentation in English and Brazilian Portuguese, kept in sync | Two audiences, one project | Accepted |
| 013 | 2026-11-22 | Remove Splunk; emit structured JSON events through structlog | The free tier is gone; stdout JSON works with any log collector | Accepted (supersedes the earlier Splunk HEC design) |
| 014 | 2026-11-22 | Chat follow-ups (compare, cheapest, price history) act on the previous results and are computed from the database | Conversation without generation, answers stay checkable | Accepted |
| 015 | 2026-11-22 | Weekly live canary against the store | The Magento migration broke the scraper silently; a cheap check notices markup changes early | Accepted |
| 016 | 2026-11-22 | Hash-locked dependencies, actions pinned by SHA, image pinned by digest, 7-day Dependabot cooldown | A compromised package or moved tag must not change what runs | Accepted |
| 017 | 2026-11-22 | SemVer starting at 0.1.0; `app/releases.yaml` as the single source of history; images published to ghcr.io with provenance and SBOM | One truth for What's new, the API and GitHub Releases | Accepted |
| 018 | 2026-11-22 | Alembic migrations replace `create_all`; existing databases are adopted by stamping a baseline | Schema changes need history and a rollback path; people already have a `garimpo.db` | Accepted |
| 019 | 2026-11-22 | Mark a product disappeared after N consecutive full crawls without it, ignoring crawls that find under half the known products | A product can stop being listed without a 404; an outage must never empty the catalog | Accepted |
| 020 | 2026-11-22 | Keep samples of pages that fail to parse and alert on a failure-rate spike | A store redesign should be debuggable in minutes, not discovered by empty data | Accepted |
| 021 | 2026-11-22 | Prune scrape runs after 90 days; keep price history forever by default | Runs are operational noise; history is the product's value | Accepted |
| 022 | 2026-11-22 | Postgres support, Redis-backed limits and catalog-learned synonyms are deferred | Not needed for a single instance; migrations are written portably so Postgres stays possible | Deferred |
| 023 | 2026-11-22 | Alerts without user accounts: a random browser id keys the watches | No passwords or e-mail to store or leak; the cost is that clearing browser data forgets them | Accepted |
| 024 | 2026-11-22 | Alert delivery through ntfy and allow-listed webhooks only; Telegram and e-mail not built in | Both need operator credentials; webhooks reach them through a bridge, and exact-host allow-listing prevents SSRF | Accepted |
| 025 | 2026-11-22 | A "deal" is a real recorded drop to the lowest price of the window, never the store's from/to price | The store's claims are not verifiable; our own history is | Accepted |
