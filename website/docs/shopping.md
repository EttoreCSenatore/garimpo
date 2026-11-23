---
sidebar_position: 6
title: Explore, deals and alerts
---

# Explore, deals and alerts

Besides the chat, the web app has two more tabs and a watch box in the product view.

## Explore

![Explore tab with filters](@site/static/img/screenshots/explore.png)

Filter by text, brand, size **in stock**, price range and whether to hide sold-out products; sort by relevance, price, popularity, newest or name; load more at the bottom. The sizes offered are the ones that actually exist in stock today. API: `GET /api/catalog` and `GET /api/facets`.

## Deals

![Deals tab](@site/static/img/screenshots/deals.png)

A deal here is a **real drop recorded by Garimpo**: the product is in stock, its current price is the lowest of the last 90 days, and it is at least 5 % below the highest price seen in that window. The store's own "from/to" prices are not used. The chat answers *ofertas* the same way. API: `GET /api/deals?days=90&min_discount=5`.

## Alerts

![Watch box with a target price](@site/static/img/screenshots/watch.png)

In a product's view, **Avisar-me** creates a watch: a notification when the price drops, when a size comes back in stock (pick the size) or when the price reaches a target. Nothing is sent for a price rise, and every price drop or restock is notified once.

There are **no accounts**. The browser keeps a random id (`X-Watcher-Id`, 22 to 64 characters) that is the only key to its watches, so clearing the browser data forgets them. Delivery channels:

- **ntfy** (default): you choose a topic name (the app suggests a random one), install the [ntfy](https://ntfy.sh) app and subscribe to it. Anyone who knows the topic name can read the alerts, so keep it private.
- **Webhook**: only for hosts the operator lists in `ALERTS_WEBHOOK_HOSTS` (for example `hooks.slack.com`); the body carries `text` (Slack) and `content` (Discord) plus JSON fields for your own endpoint.

Telegram and e-mail are not built in: they need credentials owned by the operator. A webhook to a bridge covers them meanwhile.

### Turning it on (operator)

Alerts are **off by default** because they make outbound requests from your server.

```bash
ALERTS_ENABLED=true
ALERTS_NTFY_SERVER=https://ntfy.sh          # or your own ntfy
ALERTS_WEBHOOK_HOSTS=hooks.slack.com        # empty: webhooks disabled
```

| Endpoint | What it does |
| --- | --- |
| `GET /api/alerts/config` | Whether alerts are on and which channels exist. |
| `POST /api/watches` | Create or update a watch (`product_id`, optional `size`, `target_price`, `channel`, `destination`). Needs `X-Watcher-Id`. |
| `GET /api/watches` | The caller's watches; destinations are masked (`gar…`). |
| `DELETE /api/watches/{id}` | Remove one of the caller's watches. |

### Privacy and safety

- A watch stores the ntfy topic or webhook URL the shopper typed, the product, size and target price. No name, e-mail or IP is stored. The API never returns a full destination.
- To delete everything for a person, delete their watches (`DELETE /api/watches/{id}`) or the rows of the `watches` table.
- The server contacts **only** `ALERTS_NTFY_SERVER` and the exact HTTPS hosts you allow: a shopper cannot point it at an internal address (SSRF). Webhook hosts are checked again at send time.
- Creating watches is rate limited (`WATCH_RATE_LIMIT_PER_MINUTE`) and capped per browser (`ALERTS_MAX_WATCHES_PER_WATCHER`, 20).
- A failed delivery is retried at the next scrape of that product instead of being lost.
