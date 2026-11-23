---
sidebar_position: 10
title: Upgrading
---

# Upgrading

1. Read [What's new](./versioning) (the chat footer and the GitHub release) for the target version, especially a MAJOR bump.
2. **Back up first**: `docker compose exec app python -m app.backup backup`.
3. Pull and restart:

```bash
docker compose pull          # when using the published image
docker compose up -d
curl http://127.0.0.1:8000/api/version
```

When you build locally, use `git pull && docker compose up -d --build`.

4. Check `GET /api/health` and the logs. The schema changes are applied automatically at startup (new tables and indexes only; destructive changes would be a MAJOR release with notes).

## Rolling back

Run the previous image tag (`ghcr.io/ettorecsenatore/garimpo:0.3.0`) and, if the data was changed in a way the old version cannot read, restore the backup you took in step 2 (see [Backup and restore](./backup-restore)).

## Reverse proxy with Caddy

```caddyfile
garimpo.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy gets and renews the HTTPS certificate on its own. Set `TRUST_PROXY_HEADERS=true` only when the proxy overwrites `X-Forwarded-For` (Caddy does).
