---
slug: /
sidebar_position: 1
title: Garimpo
---

# Garimpo

**Garimpo** is a catalog scraper, REST API and conversational search for a Brazilian sports e-commerce site, Tivolli Sports (tivolli.com.br).
The name is Brazilian Portuguese for prospecting: *garimpar* is what you do when you hunt for a good find or a bargain.
It keeps a local, near-real-time copy of the product catalog and lets people search it in plain Portuguese or English:
*"tênis feminino número 38"*, *"chuteiras nike até 500"*, *"camisa do flamengo"*.

![Conversational search with product cards](@site/static/img/screenshots/chat-results.png)

:::info Demo data
The screenshots in this documentation use generic demo products (`python -m app.seed`), not the store's real catalog or images.
:::

## What is in the box

| Part | What it does |
| --- | --- |
| **Scraper** | Discovers categories from `google_sitemap.xml`, crawls listings and product pages at ~1 request/second with jitter and back-off. |
| **REST API** | FastAPI service with cursor pagination, filters, price history and OpenAPI docs. |
| **Chat search** | A rule-based intent parser (no LLM, no API keys) turns a sentence into database filters and asks for gender and shoe size when needed. |
| **Frontend** | React + TypeScript + Tailwind chat UI that renders products as cards. |
| **Observability** | Structured JSON logs and domain events (scrape runs, price changes, errors) on stdout, ready for any log collector. |

## Highlights

- Polite by design: a process-wide request budget, `robots.txt` disallowed paths enforced in code, same-site URLs only.
- Secure defaults: SSRF-safe image proxy, constant-time admin token, strict CORS, rate limits, non-root container.
- Tested: a pytest suite with HTTP mocked, no network and no real database required, run by CI on every pull request.
- Documented in English and Brazilian Portuguese.

## Where to go next

- New here? Start with [Getting started](getting-started.md).
- Curious how it fits together? Read the [Architecture](architecture.md).
- Running it for real? See [Deployment](deployment.md), [Security](security.md) and [Responsible use](responsible-use.md).
