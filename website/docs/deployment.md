---
sidebar_position: 7
title: Deployment
---

# Deployment

## Docker Compose

```bash
export ADMIN_TOKEN=$(openssl rand -hex 32)
docker compose up -d --build
curl http://127.0.0.1:8000/api/health
```

The compose file is hardened by default:

- the port is published on **127.0.0.1 only**; put a TLS-terminating reverse proxy in front for public access
- `ADMIN_TOKEN` is required (no default), and `APP_ENV=production` rejects weak tokens at startup
- the container runs as an **unprivileged user** with a **read-only root filesystem**, all capabilities dropped and `no-new-privileges`
- state lives in the `garimpo_data` volume (`/app/data`): the SQLite database and the Splunk buffer
- the health check calls `/api/health` with Python, so the image contains no `curl`

## Reverse proxy

Terminate TLS in front of the app (Caddy, nginx, Traefik). If you rely on client IPs for rate limiting,
set `TRUST_PROXY_HEADERS=true` **only** when the proxy overwrites `X-Forwarded-For`.
Set `CORS_ORIGINS` to the origin that serves your frontend.

## Serving the frontend

`npm run build` in `frontend/` produces static files in `frontend/dist`. Serve them from the same origin as the API
(proxy `/api` and the data routes to the app) so no CORS configuration is needed.

## Backups

Copy the SQLite database with `sqlite3 garimpo.db ".backup backup.db"`, which is safe while the app runs in WAL mode.
The catalog can always be rebuilt by a full refresh, but price history cannot.

## Operations checklist

- [ ] Strong `ADMIN_TOKEN`, stored in your secret manager
- [ ] TLS in front, port not exposed publicly
- [ ] `USER_AGENT` identifies you; you have permission to scrape the site
- [ ] `SPLUNK_HEC_VERIFY_SSL=true` unless Splunk is local
- [ ] Backups of the data volume
