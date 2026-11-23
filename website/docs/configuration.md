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
| `DATABASE_URL` | `sqlite:///./garimpo.db` | Any SQLAlchemy URL. |
| `SCHEDULER_ENABLED` | `true` | Set `false` to disable background scraping. |
| `DISCLAIMER` | `false` | Mark prices as indicative and expose `source_url`. |

## Security

| Variable | Default | Description |
| --- | --- | --- |
| `ADMIN_TOKEN` | *(empty)* | Empty disables `/admin/*`. Must be 24+ random characters in production. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins. `*` is ignored. |
| `IMAGE_PROXY_ALLOWED_HOSTS` | `www.tivolli.com.br` | Exact hostnames the image proxy may fetch. |
| `CHAT_RATE_LIMIT_PER_MINUTE` / `IMAGE_RATE_LIMIT_PER_MINUTE` | `30` / `240` | Per-client limits; `0` disables. |
| `TRUST_PROXY_HEADERS` | `false` | Use `X-Forwarded-For` for client identity (only behind a trusted proxy). |

## Scraper

| Variable | Default | Description |
| --- | --- | --- |
| `USER_AGENT` | `GarimpoBot/1.0 (+repo URL)` | Identify your bot and give a way to contact you. |
| `BASE_URL` | `https://www.tivolli.com.br` | Site to crawl. |
| `REQUESTS_PER_SECOND` | `1` | Process-wide request budget. |
| `JITTER_MIN_MS` / `JITTER_MAX_MS` | `500` / `1500` | Random delay added to each request. |
| `MAX_RETRIES` | `3` | Retries on 429/5xx/network errors with exponential back-off. |
| `FULL_REFRESH_INTERVAL_MINUTES` | `360` | Full crawl interval. |
| `INCREMENTAL_REFRESH_INTERVAL_MINUTES` | `15` | Incremental interval. |
| `INCREMENTAL_TOP_N` | `200` | Products refreshed per incremental run. |

## Backups, heartbeats, freshness and metrics

| Variable | Default | Description |
| --- | --- | --- |
| `BACKUP_ENABLED` | `true` | Daily SQLite backup and weekly restore test (ignored for other databases). |
| `BACKUP_DIR` | *(next to the database)* | Where backups and `status.json` are kept. |
| `BACKUP_HOUR_UTC` | `6` | Hour of the daily backup; the restore test runs one hour later. |
| `BACKUP_KEEP` | `14` | Backups kept; older ones are deleted. |
| `RESTORE_TEST_WEEKDAY` | `sun` | Day of the weekly restore test. |
| `HEARTBEAT_FULL_URL`, `HEARTBEAT_INCREMENTAL_URL`, `HEARTBEAT_BACKUP_URL`, `HEARTBEAT_RESTORE_URL` | *(empty)* | Heartbeat URLs; empty disables. See [Monitoring](./monitoring). |
| `STALE_AFTER_HOURS` | `24` | `stale: true` in `/api/health` (and a banner in the chat) when no successful refresh happened within this time. |
| `BACKUP_STALE_HOURS` | `26` | The backup counts as stale after this time. |
| `METRICS_ENABLED` | `false` | Serve Prometheus metrics at `/metrics`. |
| `METRICS_TOKEN` | *(empty)* | Optional Bearer token required by `/metrics`. |
