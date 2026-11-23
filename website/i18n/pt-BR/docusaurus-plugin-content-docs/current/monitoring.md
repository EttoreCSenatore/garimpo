---
sidebar_position: 9
title: Monitoramento
---

# Monitoramento

## Está no ar e está fresco?

`GET /api/health` responde sem login:

```json
{"status": "ok", "version": "0.3.0", "last_refresh": "2026-11-22T12:00:00+00:00",
 "catalog_age_seconds": 3600, "stale": false,
 "backup": {"enabled": true, "stale": false, "last_backup_at": "...", "last_restore_test_ok": true}}
```

- `stale` é verdadeiro quando não houve atualização **bem-sucedida** em `STALE_AFTER_HOURS`; o chat mostra então um aviso para os visitantes saberem que os preços podem estar velhos.
- `backup.stale` é verdadeiro quando o último backup é mais antigo que `BACKUP_STALE_HOURS`, ou não existe.
- `GET /api/version` devolve só a versão instalada, para monitores de disponibilidade simples.

## Sinais de vida: perceber um scraper morto

Um endpoint de saúde não avisa que o agendador parou em silêncio. Os sinais de vida avisam: cada tarefa chama uma URL ao terminar, e um monitor alerta quando um sinal **falta** (o que também cobre a máquina desligada). O [Healthchecks.io](https://healthchecks.io) (plano gratuito), o Uptime Kuma ou qualquer serviço compatível serve.

Crie uma verificação por linha, com agenda **Simple**, e coloque a URL dela no `.env`:

| Variável | Período / tolerância sugeridos | Chamada quando |
| --- | --- | --- |
| `HEARTBEAT_FULL_URL` | 6 h / 2 h | uma atualização completa termina; `/fail` é chamada se der erro |
| `HEARTBEAT_INCREMENTAL_URL` | 15 min / 30 min | uma atualização incremental termina |
| `HEARTBEAT_BACKUP_URL` | 1 dia / 2 h | o backup diário dá certo |
| `HEARTBEAT_RESTORE_URL` | 7 dias / 1 dia | o teste semanal de restauração passa |

Os sinais nunca quebram uma tarefa: uma queda do monitor é registrada como `heartbeat.failed` e ignorada. Deixe a variável vazia para desativar.

## Métricas Prometheus

Defina `METRICS_ENABLED=true` (e um `METRICS_TOKEN`) para servir `/metrics`:

| Métrica | Significado |
| --- | --- |
| `garimpo_build_info{version}` | Versão instalada |
| `garimpo_products{status}` | Produtos por status |
| `garimpo_last_success_timestamp_seconds{run_type}` | Quando cada tipo de coleta teve sucesso pela última vez |
| `garimpo_last_run_failed{run_type}` | 1 quando a coleta mais recente de um tipo falhou |
| `garimpo_last_run_products_scraped` / `_failed` / `_duration_seconds` | Tamanho, falhas e duração da última coleta bem-sucedida |
| `garimpo_backup_last_success_timestamp_seconds`, `garimpo_backup_size_bytes` | Saúde do backup |
| `garimpo_restore_test_ok` | 1 quando o último teste de restauração passou |

```yaml
# prometheus.yml
scrape_configs:
  - job_name: garimpo
    authorization: {credentials: "<METRICS_TOKEN>"}
    static_configs: [{targets: ["garimpo:8000"]}]
```

Também: `garimpo_products_missing_crawls` (candidatos a desaparecimento) e `garimpo_parse_failure_samples`.

Alertas úteis: `time() - garimpo_last_success_timestamp_seconds{run_type="full"} > 8*3600`, `garimpo_last_run_failed == 1`, `garimpo_restore_test_ok == 0` e um pico de `garimpo_last_run_products_failed` (a loja mudou o HTML; o [canário](./development#canário-do-scraper) costuma avisar primeiro).

Mantenha o `/metrics` atrás do proxy reverso ou em uma rede interna.

## Quando a loja muda as páginas

1. O [canário](./development#canário-do-scraper) semanal falha, ou uma coleta completa registra `garimpo.error.parse_spike` (e chama o sinal de falha).
2. Leia as páginas com falha mais recentes: `curl -H "X-Admin-Token: $ADMIN_TOKEN" "http://127.0.0.1:8000/admin/parse-failures?limit=5&full=true"` devolve a URL, o erro, o status HTTP e o início do HTML.
3. Adicione esse HTML como fixture em `tests/fixtures/`, ajuste o parser até o teste passar e lance uma versão.

Uma página que é lida mas não tem nome de produto também conta como falha, então um redesenho não enche o catálogo de produtos vazios em silêncio.

## Logs e eventos

Tudo é JSON no stdout (`docker compose logs -f app`). Eventos de domínio: `garimpo.run.started|completed`, `garimpo.product.scraped|updated|disappeared`, `garimpo.backup.completed|restore_tested` e `garimpo.error.parse|parse_spike|crawl_incomplete|http|backup|restore_test` e `garimpo.retention.applied`.
