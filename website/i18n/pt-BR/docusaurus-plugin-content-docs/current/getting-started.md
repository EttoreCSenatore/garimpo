---
sidebar_position: 2
title: Primeiros passos
---

# Primeiros passos

## Requisitos

- Python 3.12+
- Node.js 22+ (apenas para o frontend de chat)
- Docker (opcional)

## Rodar a API localmente

```bash
git clone https://github.com/EttoreCSenatore/tivolli-sports.git
cd tivolli-sports
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Abra [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) para a documentação interativa da API.

:::caution O agendador coleta dados do site real
A menos que `SCHEDULER_ENABLED=false`, o app executa uma coleta completa cerca de um minuto após iniciar e uma incremental a cada 15 minutos.
Leia antes [Uso responsável](responsible-use.md) e use `SCHEDULER_ENABLED=false` enquanto só estiver explorando.
:::

## Experimentar com dados de demonstração (sem coletar)

```bash
export SCHEDULER_ENABLED=false
.venv/bin/python -m app.seed        # 12 produtos genéricos de demonstração
.venv/bin/python -m uvicorn app.main:app --port 8000
```

## Rodar o frontend de chat

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, faz proxy de /api para :8000
```

![Tela de boas-vindas](@site/static/img/screenshots/chat-welcome.png)

## Rodar os testes

```bash
.venv/bin/python -m pytest tests -q
```

Os testes nunca acessam a rede nem o seu `tivolli.db` local: `tests/conftest.py` usa um banco temporário e desativa o agendador.

## Rodar com Docker

```bash
export ADMIN_TOKEN=$(openssl rand -hex 32)
docker compose up --build
```

O compose se recusa a iniciar sem `ADMIN_TOKEN` e publica a porta apenas em `127.0.0.1`. Veja [Implantação](deployment.md).
