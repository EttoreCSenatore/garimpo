# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository
(https://github.com/EttoreCSenatore/garimpo/security/advisories/new).

I aim to acknowledge reports within a few days. This is a personal project maintained on a best-effort basis.

## Supported versions

Only the latest commit on `main` is supported.

## Deployment guidance

- Set `ADMIN_TOKEN` to a random value (`openssl rand -hex 32`); the app refuses to start in production without one.
- Keep the API behind a TLS-terminating reverse proxy; the compose file binds to loopback only.
- Keep `SPLUNK_HEC_VERIFY_SSL=true` except for a local, self-signed Splunk.
- Never commit `.env`, `garimpo.db` or `events.jsonl` (they are git-ignored).
- Scrape only with permission, respect `robots.txt` and the site's terms; see the README disclaimer.
