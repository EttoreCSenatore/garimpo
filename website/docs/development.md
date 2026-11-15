---
sidebar_position: 10
title: Development
---

# Development

## Layout

```text
app/            FastAPI app, scraper, search, event logging
frontend/       React + Vite + Tailwind chat UI
tests/          pytest suite (HTTP mocked with respx)
website/        This documentation (Docusaurus, English + Brazilian Portuguese)
.github/        CI, CodeQL, Dependabot, docs deployment
```

## Quality gates

```bash
ruff check .                         # lint, including security rules (flake8-bandit)
python -m pytest tests -q            # no network, temporary database
cd frontend && npx tsc --noEmit && npm run build
```

CI runs the same checks plus `pip-audit`, `npm audit` and a Docker build; CodeQL scans Python and TypeScript.

## Testing notes

- `tests/conftest.py` sets a temporary database, disables the scheduler and clears rate limiters between tests.
- Scraper tests use saved HTML fixtures in `tests/fixtures/`; image-proxy tests use `respx`.
- Never add a test that hits the real site.

## Documentation

```bash
cd website
npm ci
npm start                          # English
npm start -- --locale pt-BR        # Brazilian Portuguese
npm run build
```

Keep the two languages in sync: English lives in `website/docs/`, Portuguese in
`website/i18n/pt-BR/docusaurus-plugin-content-docs/current/`.
The docs are deployed to GitHub Pages by `.github/workflows/docs.yml` on every push to `main` that touches `website/`.

## Refreshing the screenshots

Screenshots live in `website/static/img/screenshots/` and use demo data (`python -m app.seed`) so no third-party
product images are published.
