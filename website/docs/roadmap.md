---
sidebar_position: 11
title: Roadmap
---

# Roadmap

Garimpo works end to end: a polite scraper, an API, full-text search and a chat with follow-ups. This roadmap is about making it **trustworthy to run, easy to release and pleasant to show**. Much of it is adapted from [Kaladrius](https://github.com/facchini-miguel/kaladrius), an open-source clinic management system (Django, Apache-2.0, 70+ releases) whose engineering habits are a good model.

## What Kaladrius does that we can learn from

Different product, same discipline. These are the practices worth adapting, and what we leave out.

| Area | Kaladrius | Garimpo today | Verdict |
| --- | --- | --- | --- |
| **Supply chain** | Third-party actions pinned to a commit SHA; locked dependencies with hashes (`pip-compile`); Dependabot with a 7-day cooldown; Docker images pinned by digest | Actions by tag; unpinned `>=` requirements; Dependabot grouped, no cooldown | **Adopt** (M1) |
| **CI gates** | Lint and format check, Django checks, tests with a 90 % coverage floor, docs build, link check, installs the packages in clean distros | Lint, tests, frontend build, docker build, CodeQL, docs build; no coverage floor | **Adopt** coverage floor and format check (M1) |
| **Migration safety** | A workflow reports the SQL of each migration on the PR and tests a rollback | Schema is `create_all` plus idempotent indexes, no migrations | **Adopt** once Alembic lands (M4) |
| **Releases** | SemVer, one `releases.yaml` feeding the "What's new" page, the API and GitHub Releases; image published to ghcr.io | No tags or releases; no version in the UI | **Adopt** (M2) |
| **Backups** | Daily dump, retention, a weekly automatic restore test into a throwaway database, backup status shown as a warning in the app | None documented for the SQLite file | **Adopt** (M3) |
| **Monitoring** | Healthchecks.io pings per job (system, backup, restore, update, disk, certificate): warns when a signal fails or stops arriving; Prometheus textfile metrics; `/api/v1/version` and `/health` | `/api/health` only | **Adopt** (M3); a heartbeat after each scrape fits our scheduler perfectly |
| **Decisions** | A numbered decision log with date, reason, status and superseded links | Decisions live in PR text | **Adopt** a short log (M2) |
| **Community files** | CODEOWNERS, CONTRIBUTING, Code of Conduct, SECURITY with an advisory flow | SECURITY only | **Adopt** (M1) |
| **Demo** | A public demo server that resets nightly, with logins per role | A local demo script | **Adopt** the reset idea once hosted (M6) |
| **Docs structure** | Install / operate / manual / project (vision, data model, glossary, decisions) | Good en + pt-BR guide, no operations or decision pages | **Adopt** operations and project sections (M3, M2) |
| Multi-tenant isolation, audit log of people, finance modules, RBAC | Core to a clinic system | Single catalog, no user accounts | **Not needed** |
| Trilingual UI and docs (en, pt-BR, es) | Yes | en and pt-BR | **Keep two languages** |
| Linux packages (.deb/.rpm), apt repository | Yes, for non-technical installers | Docker image | **Skip**: our audience runs containers |
| Mobile app, Django stack | Yes | React web chat | **Not applicable** |

## Milestones

Each milestone is a handful of small PRs. Order is by value for effort.

### M1: Supply chain and CI hardening (done)

- Pin every third-party GitHub Action to a commit SHA with the tag in a comment; Dependabot keeps both updated.
- Lock Python dependencies with hashes (`pip-compile --generate-hashes`, separate dev lock), and fail CI when the lock is stale.
- Dependabot `cooldown` of 7 days for version updates; security updates still arrive at once.
- Measure test coverage, then set a floor (start at the current number, raise to 90 %); add `ruff format --check`.
- `persist-credentials: false` on every checkout; keep CI permissions at `contents: read`.
- Add `CODEOWNERS`, `CONTRIBUTING.md` and a Code of Conduct.
- Pin the Docker base image by digest.

### M2: Releases, versioning and decisions

- Adopt SemVer, starting at `0.1.0`; version exposed at `GET /api/version` and in the UI footer.
- One `releases.yaml` (or `CHANGELOG`) as the source for GitHub Releases and a "What's new" docs page (en + pt-BR).
- Tagged release workflow: build and publish the container image to ghcr.io with provenance and an SBOM.
- Start a numbered decision log in the docs (SQLite first, rule-based chat, why no LLM, polite scraping, no Splunk) with date, reason and status.
- Add vision, data-model and glossary pages under a "Project" section.

### M3: Run it for real (operations)

- **Backups:** daily online SQLite backup (`.backup`), retention, and a weekly restore test into a throwaway file. Record the last backup and show a warning when it is older than 26 hours.
- **Heartbeats:** optional Healthchecks.io-style pings (URL in `.env`) after each full refresh, incremental refresh, backup and canary; silence means something stopped. This is the cheapest way to know the scraper died.
- **Metrics:** a `/metrics` endpoint or textfile (scrape duration, parse failures, products scraped, queue depth, last success timestamp).
- **Freshness in the UI:** warn visitors when the catalog is older than a threshold.
- **Docs:** an Operations section: install, upgrade, backup and restore, monitoring, logs.
- Reference deployment: compose with a TLS reverse proxy (Caddy) and a systemd timer for backups.

### M4: Data and correctness

- **Alembic migrations** replace `create_all`; add a PR workflow that prints each migration's SQL and tests upgrade then downgrade on a copy.
- **Detect disappeared products from crawls:** mark a product missing after N consecutive full crawls without it, not only on a 404.
- **Parser resilience:** keep the canary, alert when the parse failure rate spikes, store a sample of failing HTML for debugging.
- **Retention:** prune old scrape runs and compact history, as Kaladrius does for audit data.
- **PostgreSQL option** with the same migrations, for people who want more than one instance; move rate limits and chat sessions to Redis only if that happens.
- Smarter relevance: synonyms learned from the catalog.

### M5: Features for shoppers

- Filters and sorting next to the chat (size in stock, brand, price range, category).
- **Deals page:** biggest drops against the product's own price history, with "lowest in 90 days".
- **Watchlist and price-drop alerts** through ntfy, Telegram, webhook or e-mail (the same channel design Atalaia uses).
- Size-aware availability and back-in-stock alerts.

### M6: Show it (demo and portfolio)

- Hosted demo on demo data, with a nightly reset so it never drifts; the server choice is still open.
- Architecture notes and a short screencast in the README.
- Real product images only if the store grants permission.

### M7: Optional AI chat (decision pending)

- A Claude-powered mode behind an API-key setting, with tool use limited to the same grounded functions as today (search, compare, history). Needs prompt-injection guards for scraped text and a per-message cost budget. Off by default.

## How we will work

- Every change through a PR with green checks; docs updated in English and Portuguese in the same PR.
- Each milestone ends with a tagged release once M2 exists.
- Record non-obvious choices in the decision log.
