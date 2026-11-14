---
slug: /
sidebar_position: 1
title: Tivolli Sports
---

# Tivolli Sports

**Tivolli Sports** is a catalog scraper, REST API and conversational search for a Brazilian sports e-commerce site (tivolli.com.br).
It keeps a local, near-real-time copy of the product catalog and lets people search it in plain Portuguese or English:
*"tênis feminino número 38"*, *"chuteiras nike até 500"*, *"camisa do flamengo"*.

![Conversational search with product cards](@site/static/img/screenshots/chat-results.png)

:::info Demo data
The screenshots in this documentation use generic demo products (`python -m app.seed`), not the store's real catalog or images.
:::

## What is in the box

| Part | What it does |
| --- | --- |
| **Scraper** | Discovers categories from `sitemap.xml`, crawls listings and product pages at ~1 request/second with jitter and back-off. |
| **REST API** | FastAPI service with cursor pagination, filters, price history and OpenAPI docs. |
| **Chat search** | A rule-based intent parser (no LLM, no API keys) turns a sentence into database filters and asks for gender and shoe size when needed. |
| **Frontend** | React + TypeScript + Tailwind chat UI that renders products as cards. |
| **Observability** | Structured logs and Splunk HEC forwarding with an on-disk buffer when Splunk is unreachable. |

## Highlights

- Polite by design: a process-wide request budget, `robots.txt` disallowed paths enforced in code, same-site URLs only.
- Secure defaults: SSRF-safe image proxy, constant-time admin token, strict CORS, rate limits, non-root container.
- Tested: 90 automated tests with HTTP mocked, no network and no real database required.
- Documented in English and Brazilian Portuguese.

## Where to go next

- New here? Start with [Getting started](getting-started.md).
- Curious how it fits together? Read the [Architecture](architecture.md).
- Running it for real? See [Deployment](deployment.md), [Security](security.md) and [Responsible use](responsible-use.md).
