---
sidebar_position: 9
title: Monitoring
---

# Monitoring

## Is it up, and is it fresh?

`GET /api/health` answers without login:

```json
{"status": "ok", "version": "0.3.0", "last_refresh": "2026-11-22T12:00:00+00:00",
 "catalog_age_seconds": 3600, "stale": false,
 "backup": {"enabled": true, "stale": false, "last_backup_at": "...", "last_restore_test_ok": true}}
```

- `stale` is true when no **successful** refresh happened within `STALE_AFTER_HOURS`; the chat then shows a banner so visitors know prices may be old.
- `backup.stale` is true when the last backup is older than `BACKUP_STALE_HOURS`, or there is none.
- `GET /api/version` returns only the installed version, for plain uptime monitors.

## Heartbeats: noticing a dead scraper

A health endpoint cannot tell you the scheduler silently stopped. Heartbeats can: each job pings a URL when it finishes, and a monitor alerts when a ping is **missing** (which also covers the whole machine being off). [Healthchecks.io](https://healthchecks.io) (free plan), Uptime Kuma or any compatible service works.

Create one check per line, with the **Simple** schedule, and put its ping URL in `.env`:

| Variable | Suggested period / grace | Pinged when |
| --- | --- | --- |
| `HEARTBEAT_FULL_URL` | 6 h / 2 h | a full refresh completes; `/fail` is called when it errors |
| `HEARTBEAT_INCREMENTAL_URL` | 15 min / 30 min | an incremental refresh completes |
| `HEARTBEAT_BACKUP_URL` | 1 day / 2 h | the daily backup succeeds |
| `HEARTBEAT_RESTORE_URL` | 7 days / 1 day | the weekly restore test passes |

Pings never break a job: a monitor outage is logged as `heartbeat.failed` and ignored. Leave a variable empty to disable it.

## Prometheus metrics

Set `METRICS_ENABLED=true` (and a `METRICS_TOKEN`) to serve `/metrics`:

| Metric | Meaning |
| --- | --- |
| `garimpo_build_info{version}` | Installed version |
| `garimpo_products{status}` | Products by status |
| `garimpo_last_success_timestamp_seconds{run_type}` | When each kind of run last succeeded |
| `garimpo_last_run_failed{run_type}` | 1 when the latest run of a type failed |
| `garimpo_last_run_products_scraped` / `_failed` / `_duration_seconds` | Size, failures and duration of the last successful run |
| `garimpo_backup_last_success_timestamp_seconds`, `garimpo_backup_size_bytes` | Backup health |
| `garimpo_restore_test_ok` | 1 when the last restore test passed |

```yaml
# prometheus.yml
scrape_configs:
  - job_name: garimpo
    authorization: {credentials: "<METRICS_TOKEN>"}
    static_configs: [{targets: ["garimpo:8000"]}]
```

Useful alerts: `time() - garimpo_last_success_timestamp_seconds{run_type="full"} > 8*3600`, `garimpo_last_run_failed == 1`, `garimpo_restore_test_ok == 0`, and a spike of `garimpo_last_run_products_failed` (the store changed its markup; the [canary](./development#scraper-canary) usually says so first).

Keep `/metrics` behind your reverse proxy or on an internal network.

## Logs and events

Everything is JSON on stdout (`docker compose logs -f app`). Domain events: `garimpo.run.started|completed`, `garimpo.product.scraped|updated|disappeared`, `garimpo.backup.completed|restore_tested`, and `garimpo.error.parse|http|backup|restore_test`.
