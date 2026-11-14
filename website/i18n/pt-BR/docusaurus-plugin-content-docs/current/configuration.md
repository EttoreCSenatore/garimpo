---
sidebar_position: 6
title: Configuração
---

# Configuração

As configurações vêm de variáveis de ambiente ou de um arquivo `.env` (veja `.env.example`). Os nomes não diferenciam maiúsculas de minúsculas.

## Aplicação

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` ativa validação estrita (veja `ADMIN_TOKEN`). |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Endereço de escuta. Contêineres usam `HOST=0.0.0.0`. |
| `DATABASE_URL` | `sqlite:///./garimpo.db` | Qualquer URL do SQLAlchemy. |
| `SCHEDULER_ENABLED` | `true` | Use `false` para desativar a coleta em segundo plano. |
| `DISCLAIMER` | `false` | Marca preços como indicativos e expõe `source_url`. |

## Segurança

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `ADMIN_TOKEN` | *(vazio)* | Vazio desativa `/admin/*`. Em produção deve ter 24+ caracteres aleatórios. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Origens de navegador permitidas, separadas por vírgula. `*` é ignorado. |
| `IMAGE_PROXY_ALLOWED_HOSTS` | `www.tivolli.com.br` | Hostnames exatos que o proxy de imagens pode acessar. |
| `CHAT_RATE_LIMIT_PER_MINUTE` / `IMAGE_RATE_LIMIT_PER_MINUTE` | `30` / `240` | Limites por cliente; `0` desativa. |
| `TRUST_PROXY_HEADERS` | `false` | Usa `X-Forwarded-For` para identificar o cliente (somente atrás de proxy confiável). |

## Scraper

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `USER_AGENT` | `GarimpoBot/1.0 (+URL do repositório)` | Identifique seu bot e informe um meio de contato. |
| `BASE_URL` | `https://www.tivolli.com.br` | Site a ser percorrido. |
| `REQUESTS_PER_SECOND` | `1` | Orçamento de requisições global ao processo. |
| `JITTER_MIN_MS` / `JITTER_MAX_MS` | `500` / `1500` | Atraso aleatório somado a cada requisição. |
| `MAX_RETRIES` | `3` | Novas tentativas em 429/5xx/erros de rede, com espera exponencial. |
| `FULL_REFRESH_INTERVAL_MINUTES` | `360` | Intervalo da coleta completa. |
| `INCREMENTAL_REFRESH_INTERVAL_MINUTES` | `15` | Intervalo da incremental. |
| `INCREMENTAL_TOP_N` | `200` | Produtos atualizados por execução incremental. |

## Splunk

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SPLUNK_HEC_URL` | `https://localhost:8088/services/collector/event` | Endpoint do HEC. |
| `SPLUNK_HEC_TOKEN` | *(vazio)* | Sem token, os eventos ficam no arquivo de buffer. |
| `SPLUNK_HEC_VERIFY_SSL` | `true` | Desative apenas para um Splunk local com certificado autoassinado. |
| `SPLUNK_HEC_BATCH_SIZE` | `50` | Eventos por requisição. |
| `SPLUNK_BUFFER_FILE` / `SPLUNK_BUFFER_MAX_LINES` | `events.jsonl` / `10000` | Local e limite do buffer offline (os mais novos são mantidos). |

:::note Confirmação de indexação do Splunk
Crie o token HEC com **Indexer Acknowledgment desativado**. O cliente não envia o id de canal que essa confirmação exige, então o Splunk rejeitaria todos os lotes.
:::
