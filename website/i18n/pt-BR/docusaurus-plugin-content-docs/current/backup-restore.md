---
sidebar_position: 8
title: Backup e restauração
---

# Backup e restauração

Todo o estado é um arquivo SQLite (`/app/data/garimpo.db` no contêiner): produtos, histórico de preços e coletas. **Um backup só vale se restaura**, então o Garimpo testa isso por você.

## O que roda sozinho

Com o agendador ligado, o app:

- faz um **backup online** todo dia em `BACKUP_HOUR_UTC` (06:00 UTC), com a API de backup do SQLite, então é seguro enquanto o app grava;
- verifica a cópia (`PRAGMA integrity_check`, tabelas obrigatórias) antes de guardá-la;
- mantém os `BACKUP_KEEP` (14) mais novos e apaga o resto;
- todo domingo, uma hora depois, **restaura o backup mais novo em um arquivo descartável** e confere de novo;
- registra o resultado em `status.json`, mostra em `GET /api/health` (`backup.stale`, `backup.last_restore_test_ok`) e nas métricas, e avisa as URLs de sinal de vida.

Os backups ficam em `backups/` ao lado do banco (`/app/data/backups` no contêiner, no volume `garimpo_data`), com permissão `600`.

## Manualmente

```bash
docker compose exec app python -m app.backup backup         # fazer backup agora
docker compose exec app python -m app.backup test-restore   # restaurar o mais novo em arquivo descartável e conferir
docker compose exec app python -m app.backup status         # o que a API informa
```

## Restaurando

Pare o app, coloque o backup escolhido no lugar do arquivo do banco e inicie de novo:

```bash
docker compose stop app
docker run --rm -v garimpo_garimpo_data:/data alpine sh -c \
  'cp /data/backups/garimpo-YYYYmmdd-HHMMSS.db /data/garimpo.db && rm -f /data/garimpo.db-wal /data/garimpo.db-shm && chown 10001:10001 /data/garimpo.db'
docker compose start app
```

(O nome do volume começa com o nome do projeto do compose; confira com `docker volume ls`.) O catálogo se atualiza sozinho de novo na próxima execução agendada.

:::warning
Um backup no mesmo disco não sobrevive à perda da máquina. Copie `backups/` para outro lugar todo dia (outro servidor, armazenamento de objetos com `rclone`, um disco externo criptografado). Os arquivos guardam todo o catálogo e o histórico: mantenha-os privados.
:::

## PostgreSQL ou outros bancos

O backup embutido só trata SQLite e se desliga para outros bancos. Use as ferramentas do próprio banco (`pg_dump`) nesse caso.
