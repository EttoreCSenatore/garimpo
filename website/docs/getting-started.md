---
sidebar_position: 2
title: Getting started
---

# Getting started

## Requirements

- Python 3.12+
- Node.js 22+ (only for the chat frontend)
- Docker (optional)

## Run the API locally

```bash
git clone https://github.com/EttoreCSenatore/garimpo.git
cd garimpo
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API documentation.

:::caution The scheduler scrapes the real site
Unless `SCHEDULER_ENABLED=false`, the app runs a full scrape about one minute after startup and an incremental one every 15 minutes.
Read [Responsible use](responsible-use.md) first, and set `SCHEDULER_ENABLED=false` while you only want to explore.
:::

## Try it with demo data (no scraping)

```bash
export SCHEDULER_ENABLED=false
.venv/bin/python -m app.seed        # 12 generic demo products
.venv/bin/python -m uvicorn app.main:app --port 8000
```

## Run the chat frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies /api to :8000
```

![Welcome screen](@site/static/img/screenshots/chat-welcome.png)

## Run the tests

```bash
.venv/bin/python -m pytest tests -q
```

Tests never touch the network or your local `garimpo.db`: `tests/conftest.py` uses a temporary database and disables the scheduler.

## Run with Docker

```bash
export ADMIN_TOKEN=$(openssl rand -hex 32)
docker compose up --build
```

The compose file refuses to start without `ADMIN_TOKEN` and publishes the port on `127.0.0.1` only. See [Deployment](deployment.md).
