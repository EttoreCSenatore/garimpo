#!/usr/bin/env bash
# Run Garimpo with demo data and no scraping: API on :8000, chat UI on :5173.
# Uses a throwaway database in a temp dir; your real garimpo.db is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm ci --silent)

DEMO_DIR="$(mktemp -d)"
export DATABASE_URL="sqlite:///$DEMO_DIR/demo.db" SCHEDULER_ENABLED=false
.venv/bin/python -m app.seed

.venv/bin/python -m uvicorn app.main:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null; rm -rf "$DEMO_DIR"' EXIT

echo "API:  http://127.0.0.1:8000/docs"
echo "Chat: http://localhost:5173  (try: 'tênis de corrida', then 'compare os 3 primeiros')"
cd frontend && npm run dev
