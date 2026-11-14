---
sidebar_position: 6
title: Configuration
---

# Configuration

Settings come from environment variables or a `.env` file (see `.env.example`). Names are case-insensitive.

## Application

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` enables strict validation (see `ADMIN_TOKEN`). |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Bind address. Containers set `HOST=0.0.0.0`. |
| `DATABASE_URL` | `sqlite:///./tivolli.db` | Any SQLAlchemy URL. |
| `SCHEDULER_ENABLED` | `true` | Set `false` to disable background scraping. |
| `DISCLAIMER` | `false` | Mark prices as indicative and expose `source_url`. |

## Security

| Variable | Default | Description |
| --- | --- | --- |
| `ADMIN_TOKEN` | *(empty)* | Empty disables `/admin/*`. Must be 24+ random characters in production. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins. `*` is ignored. |
| `IMAGE_PROXY_ALLOWED_HOSTS` | `estatico.tivollisports.com.br,www.tivolli.com.br` | Exact hostnames the image proxy may fetch. |
| `CHAT_RATE_LIMIT_PER_MINUTE` / `IMAGE_RATE_LIMIT_PER_MINUTE` | `30` / `240` | Per-client limits; `0` disables. |
| `TRUST_PROXY_HEADERS` | `false` | Use `X-Forwarded-For` for client identity (only behind a trusted proxy). |

## Scraper

| Variable | Default | Description |
| --- | --- | --- |
| `USER_AGENT` | `TivolliBot/1.0 (+repo URL)` | Identify your bot and give a way to contact you. |
| `BASE_URL` | `https://www.tivolli.com.br` | Site to crawl. |
| `REQUESTS_PER_SECOND` | `1` | Process-wide request budget. |
| `JITTER_MIN_MS` / `JITTER_MAX_MS` | `500` / `1500` | Random delay added to each request. |
| `MAX_RETRIES` | `3` | Retries on 429/5xx/network errors with exponential back-off. |
| `FULL_REFRESH_INTERVAL_MINUTES` | `360` | Full crawl interval. |
| `INCREMENTAL_REFRESH_INTERVAL_MINUTES` | `15` | Incremental interval. |
| `INCREMENTAL_TOP_N` | `200` | Products refreshed per incremental run. |

## Splunk

| Variable | Default | Description |
| --- | --- | --- |
| `SPLUNK_HEC_URL` | `https://localhost:8088/services/collector/event` | HEC endpoint. |
| `SPLUNK_HEC_TOKEN` | *(empty)* | Without a token events are kept in the buffer file. |
| `SPLUNK_HEC_VERIFY_SSL` | `true` | Disable only for a local self-signed Splunk. |
| `SPLUNK_HEC_BATCH_SIZE` | `50` | Events per request. |
| `SPLUNK_BUFFER_FILE` / `SPLUNK_BUFFER_MAX_LINES` | `events.jsonl` / `10000` | Offline buffer location and cap (newest kept). |
