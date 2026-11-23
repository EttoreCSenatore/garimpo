---
sidebar_position: 8
title: Backup and restore
---

# Backup and restore

The whole state is one SQLite file (`/app/data/garimpo.db` in the container): products, price history and scrape runs. **A backup only counts if it restores**, so Garimpo tests that for you.

## What runs by itself

With the scheduler on, the app:

- takes an **online backup** every day at `BACKUP_HOUR_UTC` (06:00 UTC), using SQLite's backup API, so it is safe while the app writes;
- verifies the copy (`PRAGMA integrity_check`, the required tables) before it keeps it;
- keeps the newest `BACKUP_KEEP` (14) and deletes the rest;
- every Sunday, one hour later, **restores the newest backup into a throwaway file** and checks it again;
- records the result in `status.json`, shows it in `GET /api/health` (`backup.stale`, `backup.last_restore_test_ok`) and in the metrics, and pings the heartbeat URLs.

Backups live in `backups/` next to the database (`/app/data/backups` in the container, in the `garimpo_data` volume), with mode `600`.

## By hand

```bash
docker compose exec app python -m app.backup backup         # back up now
docker compose exec app python -m app.backup test-restore   # restore the newest into a throwaway file and check it
docker compose exec app python -m app.backup status         # what the API reports
```

## Restoring

Stop the app, put the chosen backup in place of the database file, start it again:

```bash
docker compose stop app
docker run --rm -v garimpo_garimpo_data:/data alpine sh -c \
  'cp /data/backups/garimpo-YYYYmmdd-HHMMSS.db /data/garimpo.db && rm -f /data/garimpo.db-wal /data/garimpo.db-shm && chown 10001:10001 /data/garimpo.db'
docker compose start app
```

(The volume name starts with your compose project name; check it with `docker volume ls`.) The catalog refreshes itself again at the next scheduled run.

:::warning
A backup on the same disk does not survive losing the machine. Copy `backups/` somewhere else every day (another server, object storage with `rclone`, an encrypted external disk). The files hold the whole catalog and history: keep them private.
:::

## PostgreSQL or other databases

The built-in backup only handles SQLite and turns itself off for other databases. Use your database's own tooling (`pg_dump`) there.
