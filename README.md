# Tivolli Scraper + API + Splunk HEC

Production-ready web scraper and REST API for the Brazilian e-commerce site **tivolli.com.br**, with near-real-time catalog freshness and Splunk HEC event forwarding.

> **Responsible-Use Disclaimer**: This software scrapes publicly available catalog data from tivolli.com.br. The operator **must verify they have legal permission** to scrape this site before running it. Respect `robots.txt`, rate limits, and the site's terms of service. Do not collect personal/customer data. The disallowed paths `/tivadm43` and `/homologacao` are never accessed.

## Features

- **Category discovery** via `sitemap.xml` (hourly)
- **Listing crawler** with pagination (`/c/{id}-{slug}?p=N`)
- **Product detail parser** extracting price, boleto price, installments, sizes, stock, images, breadcrumbs
- **REST API** with FastAPI + OpenAPI docs, cursor pagination, caching
- **Splunk HEC integration** with batching, retries, and local buffer fallback
- **APScheduler** for full (6h) and incremental (15min) refreshes
- **SQLite** (WAL mode) via SQLModel
- **Rate limiting**: max 1 req/s with 500–1500ms jitter and exponential backoff

## Project Structure

```
tivolli-scraper/
├── app/
│   ├── main.py              # FastAPI app + APScheduler
│   ├── config.py            # pydantic-settings
│   ├── models.py            # SQLModel: Product, Category, ScrapeRun, ProductHistory
│   ├── db.py                # SQLModel engine + WAL
│   ├── splunk_hec.py        # Async HEC client
│   ├── tasks.py             # APScheduler jobs
│   ├── scraper/
│   │   ├── client.py        # Rate-limited httpx + jitter
│   │   ├── categories.py    # sitemap.xml → categories
│   │   ├── listings.py      # /c/{id}-{slug}?p=N pages
│   │   └── products.py      # product detail parser
│   └── api/
│       ├── routes.py        # FastAPI endpoints
│       └── dependencies.py  # DB session, admin auth
├── tests/
│   ├── fixtures/            # sample HTML
│   ├── test_scraper.py
│   ├── test_api.py
│   └── test_splunk.py
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Setup (Local)

### Prerequisites

- Python 3.12+
- pip

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs

## Run with Docker

```bash
docker compose up --build
```

API available at http://localhost:8000, docs at http://localhost:8000/docs.

## Environment Variables

See [.env.example](.env.example) for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `USER_AGENT` | `TivolliBot/1.0 (...)` | Crawler User-Agent |
| `REQUESTS_PER_SECOND` | `1` | Global rate limit |
| `DATABASE_URL` | `sqlite:///./tivolli.db` | SQLite path |
| `ADMIN_TOKEN` | *(empty)* | Admin API token. Empty disables `/admin/*`; must be 24+ random characters when `APP_ENV=production` |
| `SPLUNK_HEC_URL` | `https://localhost:8088/services/collector/event` | HEC endpoint |
| `SPLUNK_HEC_TOKEN` | _(empty)_ | HEC token |
| `DISCLAIMER` | `false` | If `true`, prices marked "indicative" |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check + last refresh |
| `GET` | `/products` | List products (filters: category, brand, price, available, q) |
| `GET` | `/products/{id}` | Single product (triggers background refresh if stale) |
| `GET` | `/products/{id}/history` | Price/stock history |
| `GET` | `/categories` | Categories with product counts |
| `GET` | `/stats` | Scraper stats (24h) |
| `POST` | `/admin/refresh` | Trigger full refresh (header `X-Admin-Token`) |
| `POST` | `/admin/refresh/{id}` | Refresh single product |
| `GET` | `/admin/queue` | Queue depth + active workers |

### Example curl

```bash
curl http://localhost:8000/
curl "http://localhost:8000/products?limit=10&available=true"
curl http://localhost:8000/products/12345
curl -X POST http://localhost:8000/admin/refresh -H "X-Admin-Token: your-token"
```

## Configuring Splunk Free

1. In Splunk Free: **Settings → Data Inputs → HTTP Event Collector → New Token**.
   - Name it `tivolli-scraper`.
   - Enable **Indexer Acknowledgment**.
   - Leave index as `main` (or create a `tivolli` index).
2. Copy the generated token into `.env` as `SPLUNK_HEC_TOKEN`.
3. (Self-signed certs, local Splunk Free only) set `SPLUNK_HEC_VERIFY_SSL=false`. Keep it `true` (the default) for anything else.

### Sample Search

```
sourcetype=tivolli | stats count by event_type | sort -count
```

### Sample Alert: >5% products disappeared in a run

```
sourcetype=tivolli event_type=tivolli.run.completed
| eval disappear_pct = (products_disappeared / products_scraped) * 100
| where disappear_pct > 5
| table _time run_id products_scraped products_disappeared disappear_pct
```

## Testing

```bash
pytest tests/ -v
```

## Freshness Strategy

- **Full catalog refresh**: every 6 hours
- **Incremental refresh** (top 200 most-viewed): every 15 minutes
- **On-demand**: `GET /products/{id}` revalidates in background if data > 5 min old

---

## 🤖 AI Chat Frontend

A conversational search interface powered by a pure-Python intent parser — **no LLM API keys required**.

### Frontend Setup

> **Prerequisites**: Node.js 18+ and npm.

```bash
cd frontend
npm install
npm run dev
```

Frontend available at **http://localhost:5173** — API requests are proxied to `http://localhost:8000`.

### New API Endpoint

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Conversational search — natural language → products |

**Request body:**
```json
{ "message": "tênis de corrida nike under 400", "session_id": "uuid" }
```

**Response:**
```json
{
  "reply": "I found 8 products in running from Nike under R$ 400. Here are the best matches:",
  "filters_applied": { "category": ["running"], "brand": "Nike", "price_max": 400 },
  "products": [ ...Product objects... ]
}
```

### Query Examples the AI Understands

| Query | What it extracts |
|---|---|
| `tênis de corrida` | category = running |
| `chuteiras nike` | category = futebol, brand = Nike |
| `nike under 400` | brand = Nike, price_max = 400 |
| `tênis adidas abaixo de 500` | brand = Adidas, price_max = 500 |
| `raquetes yonex` | category = tenis, brand = Yonex |
| `tênis disponível` | available = true |
| `asics acima de 200` | brand = Asics, price_min = 200 |
| `running shoes between 200 and 600` | category = running, price range 200–600 |

### Project Structure (updated)

```
tivolli-scraper/
├── app/
│   ├── search/
│   │   ├── __init__.py
│   │   └── intent_parser.py     # Smart Intent Parser (pure Python)
│   └── api/
│       └── routes.py            # + POST /api/chat endpoint
├── frontend/                    # Vite + React + TypeScript + Tailwind
│   ├── src/
│   │   ├── api.ts               # fetch wrapper
│   │   ├── types.ts             # shared TypeScript types
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css            # Tailwind directives + animations
│   │   ├── components/
│   │   │   ├── ChatBubble.tsx   # user/bot message bubbles
│   │   │   ├── ProductCard.tsx  # product card with image, price, stock
│   │   │   └── TypingIndicator.tsx
│   │   └── pages/
│   │       └── ChatPage.tsx     # main chat layout
│   ├── index.html
│   ├── vite.config.ts           # proxy /api → localhost:8000
│   ├── tailwind.config.js
│   └── package.json
└── ...
```
