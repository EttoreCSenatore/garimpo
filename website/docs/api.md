---
sidebar_position: 4
title: REST API
---

# REST API

Interactive documentation is served by the API itself at `/docs` (Swagger UI) and `/openapi.json`.

![Swagger UI](@site/static/img/screenshots/api-docs.png)

## Public endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` (also `/` and `/api/`) | Liveness plus the time of the last completed refresh. |
| GET | `/products` | List products. Filters: `category_id`, `brand`, `min_price`, `max_price`, `available`, `q`. Cursor pagination with `cursor` and `limit` (1–200). |
| GET | `/products/{id}` | One product. Increments its view counter and queues a refresh if the data is older than 5 minutes. |
| GET | `/products/{id}/history` | Price and availability history. |
| GET | `/categories` | Categories with product counts. |
| GET | `/stats` | Totals and 24-hour scrape success rate. |
| POST | `/api/chat` | Conversational search (see [Chat search](chat-search.md)). |
| GET | `/api/image-proxy?url=` | Proxy for allow-listed product images. |

Example:

```bash
curl "http://127.0.0.1:8000/products?brand=Nike&max_price=500&available=true&limit=10"
```

```json
{
  "items": [{ "id": 123, "name": "Tênis Nike ...", "price": "399.90", "available": true }],
  "next_cursor": "123",
  "total": 42
}
```

`q` is a full-text search (SQLite FTS5) over name, brand, category breadcrumbs and slug: accents and case are ignored, words can come in any order, and each word also matches as a prefix (`bol` finds *bola* and *bolas*). Every word must match. On databases without FTS5 it falls back to a literal name match. Responses carry `Cache-Control: public, max-age=60`.

## Admin endpoints

Require the header `X-Admin-Token`. They are **disabled when `ADMIN_TOKEN` is empty**.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/admin/refresh` | Start a full refresh (ignored if one is already running). |
| POST | `/admin/refresh/{id}` | Refresh one product. |
| GET | `/admin/queue` | Active workers, in-flight refreshes and chat session count. |

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://127.0.0.1:8000/admin/refresh
```

## Shopping and alerts

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/catalog` | Filter (`q`, `brand`, `category_id`, `min_price`, `max_price`, `size`, `in_stock`), sort (`sort`) and page (`offset`, `limit`) the catalog. |
| GET | `/api/facets` | Brands, sizes in stock, categories and the price range, for building filters. |
| GET | `/api/deals` | Products at their lowest recorded price of the last `days` days, biggest drop first. |
| GET | `/api/alerts/config` | Whether alerts are enabled and which channels exist. |
| POST / GET / DELETE | `/api/watches` | Manage watches (header `X-Watcher-Id`). See [Explore, deals and alerts](./shopping). |

## Errors and limits

- `401` invalid or missing admin token, `422` invalid parameters, `429` rate limit exceeded (with `Retry-After`).
- Chat messages are limited to 500 characters; session ids must match `[A-Za-z0-9_-]{1,64}`.
- Setting `DISCLAIMER=true` marks prices as indicative and adds a `source_url` to each product.
