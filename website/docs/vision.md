---
sidebar_position: 14
title: Vision
---

# Vision

*Garimpar* is Portuguese for hunting for a good find. Garimpo keeps a fresh, searchable copy of an online store's catalog and lets people dig through it in plain language, without ever hammering the store.

## Principles

- **Polite first.** One shared request budget, robots.txt in code, an honest user agent. If the store objects, the scraper stops.
- **Grounded answers.** The chat reads the database; it never invents a price, size or stock level.
- **Secure by default.** Untrusted HTML and untrusted chat text both go through validation; production refuses weak configuration.
- **Small and operable.** One process, one SQLite file, one container; easy to back up, upgrade and understand.
- **Open.** MIT license, public decisions, English and Portuguese docs.

## Who it is for

- **Shoppers** who want to find a size, compare options and see whether a price is really a deal.
- **Developers and operators** who want a clean example of a respectful scraper with an API, tests, CI and releases.

## Not goals

Reselling the store's data, bypassing its rules, collecting personal data, or replacing the store's own site for checkout.

See the [roadmap](./roadmap) for what comes next.
