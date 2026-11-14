---
sidebar_position: 7
title: Implantação
---

# Implantação

## Docker Compose

```bash
export ADMIN_TOKEN=$(openssl rand -hex 32)
docker compose up -d --build
curl http://127.0.0.1:8000/api/health
```

O arquivo compose já vem endurecido:

- a porta é publicada **somente em 127.0.0.1**; coloque um proxy reverso com TLS na frente para acesso público
- `ADMIN_TOKEN` é obrigatório (sem valor padrão), e `APP_ENV=production` rejeita tokens fracos na inicialização
- o contêiner roda como **usuário sem privilégios**, com **sistema de arquivos raiz somente leitura**, todas as capabilities removidas e `no-new-privileges`
- o estado fica no volume `garimpo_data` (`/app/data`): o banco SQLite e o buffer do Splunk
- o health check chama `/api/health` com Python, então a imagem não contém `curl`

## Proxy reverso

Termine o TLS na frente do app (Caddy, nginx, Traefik). Se você depende do IP do cliente para limitar a taxa,
use `TRUST_PROXY_HEADERS=true` **somente** quando o proxy sobrescrever `X-Forwarded-For`.
Defina `CORS_ORIGINS` com a origem que serve o seu frontend.

## Servindo o frontend

`npm run build` em `frontend/` gera arquivos estáticos em `frontend/dist`. Sirva-os na mesma origem da API
(encaminhe `/api` e as rotas de dados para o app) para não precisar configurar CORS.

## Backups

Copie o banco SQLite com `sqlite3 garimpo.db ".backup backup.db"`, o que é seguro com o app rodando em modo WAL.
O catálogo sempre pode ser reconstruído por uma atualização completa, mas o histórico de preços não.

## Checklist de operação

- [ ] `ADMIN_TOKEN` forte, guardado no seu gerenciador de segredos
- [ ] TLS na frente, porta não exposta publicamente
- [ ] `USER_AGENT` identifica você; você tem permissão para coletar dados do site
- [ ] `SPLUNK_HEC_VERIFY_SSL=true`, a menos que o Splunk seja local
- [ ] Backups do volume de dados
