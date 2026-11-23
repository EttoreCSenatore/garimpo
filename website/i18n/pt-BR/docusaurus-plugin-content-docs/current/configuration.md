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

## Qualidade dos dados e retenção

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `DISAPPEAR_AFTER_CRAWLS` | `3` | Coletas completas seguidas sem um produto antes de marcá-lo como desaparecido. |
| `DISAPPEAR_MIN_RATIO` | `0.5` | Uma coleta que encontra uma fatia menor dos produtos conhecidos é tratada como quebrada e ignorada. |
| `PARSE_FAILURE_ALERT_RATIO` / `PARSE_FAILURE_ALERT_MIN` | `0.2` / `10` | Uma coleta completa com pelo menos essas tentativas e taxa de falha maior emite `garimpo.error.parse_spike` e envia o sinal de falha. |
| `PARSE_FAILURE_SAMPLES_KEEP` / `PARSE_SAMPLE_BYTES` | `50` / `20000` | Quantas páginas com falha ficam para o `GET /admin/parse-failures` e quanto HTML de cada. |
| `RETENTION_RUNS_DAYS` | `90` | Coletas finalizadas mais antigas que isso são apagadas diariamente (0 mantém tudo). |
| `RETENTION_HISTORY_DAYS` | `0` | O histórico de preços mais antigo que isso é apagado (0, o padrão, mantém para sempre). |

## Backups, sinais de vida, frescor e métricas

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `BACKUP_ENABLED` | `true` | Backup diário do SQLite e teste semanal de restauração (ignorado para outros bancos). |
| `BACKUP_DIR` | *(ao lado do banco)* | Onde ficam os backups e o `status.json`. |
| `BACKUP_HOUR_UTC` | `6` | Hora do backup diário; o teste de restauração roda uma hora depois. |
| `BACKUP_KEEP` | `14` | Backups mantidos; os mais antigos são apagados. |
| `RESTORE_TEST_WEEKDAY` | `sun` | Dia do teste semanal de restauração. |
| `HEARTBEAT_FULL_URL`, `HEARTBEAT_INCREMENTAL_URL`, `HEARTBEAT_BACKUP_URL`, `HEARTBEAT_RESTORE_URL` | *(vazio)* | URLs de sinal de vida; vazio desativa. Veja [Monitoramento](./monitoring). |
| `STALE_AFTER_HOURS` | `24` | `stale: true` em `/api/health` (e um aviso no chat) quando não houve atualização bem-sucedida nesse prazo. |
| `BACKUP_STALE_HOURS` | `26` | O backup é considerado atrasado após esse prazo. |
| `METRICS_ENABLED` | `false` | Serve métricas Prometheus em `/metrics`. |
| `METRICS_TOKEN` | *(vazio)* | Token Bearer opcional exigido pelo `/metrics`. |
