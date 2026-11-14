---
sidebar_position: 8
title: Security
---

# Security

This page lists the protections built into the project and what to do when deploying it.
To report a vulnerability, use the repository's private advisory form (see `SECURITY.md`).

## Built-in protections

| Risk | Mitigation |
| --- | --- |
| **SSRF through the image proxy** | The request host always comes from an exact-match allow-list (never from the caller), https only, no IP literals, every redirect re-validated, 5 MB cap, only raster image types (no SVG/HTML). |
| **Admin access** | Constant-time token comparison, no default token, endpoints disabled when unset, startup fails in production with a weak token. |
| **Cross-site requests** | CORS limited to configured origins, no credentials. |
| **Browser hardening** | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and a restrictive CSP on API responses. |
| **XSS** | Chat replies are rendered as React nodes, not HTML; product and image URLs must be `http(s)`. |
| **Malicious source data** | Scraped links must be same-site `http(s)`; `javascript:` and foreign hosts are dropped. The sitemap is parsed with entities, DTDs and network access disabled. |
| **Abuse and DoS** | Per-client rate limits, bounded chat sessions, request size limits, one crawler at a time, capped in-flight refreshes. |
| **Injection** | ORM with bound parameters; user text used in `LIKE` is escaped. |
| **Secrets** | `.env`, databases and buffers are git-ignored; secret scanning and push protection are enabled on the repository. |
| **Supply chain** | Dependabot, `pip-audit` and `npm audit` in CI, CodeQL on every pull request. |
| **Container** | Non-root, read-only filesystem, no capabilities, loopback port binding. |

## Known limits

- Rate limiting is **in-process** and keyed by client address; run a single instance or add a proxy-level limit when scaling out.
- The image proxy trusts DNS for the allow-listed hostnames.
- There is no user authentication; the public API is read-only and unauthenticated by design.

## Reporting

Please do not open public issues for vulnerabilities. Use **Security → Report a vulnerability** on the GitHub repository.
