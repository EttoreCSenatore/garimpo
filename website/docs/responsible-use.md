---
sidebar_position: 9
title: Responsible use
---

# Responsible use

This software scrapes publicly available catalog data from tivolli.com.br. It is a portfolio and learning project.

:::warning Before you run it
You must have permission to scrape the site, and you are responsible for complying with its terms of service,
`robots.txt` and applicable law (including the LGPD in Brazil).
:::

## What the project does to be a good citizen

- **Identifies itself** with a descriptive `User-Agent`; set a contact URL you control.
- **Rate limits** to about one request per second process-wide, with random jitter and exponential back-off on 429/5xx.
- **Respects disallowed paths**: `/tivadm43` and `/homologacao` are blocked in code, not just by convention.
- **Stays on the site**: only same-site `http(s)` URLs are fetched, and listings come from the sitemap.
- **Collects no personal data**: only public product information (names, prices, stock, images).
- **Refreshes sparingly**: the incremental job only re-fetches the most viewed products.

## What you should do

- Ask the site owner for permission, or use an official feed or API if one exists.
- Keep the request rate low; do not shorten the jitter or raise `REQUESTS_PER_SECOND` without agreement.
- Do not republish product images or text commercially; link to the source page (`DISCLAIMER=true` helps).
- Treat prices as indicative: they may be stale.
