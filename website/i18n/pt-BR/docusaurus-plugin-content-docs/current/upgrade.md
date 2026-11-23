---
sidebar_position: 10
title: Atualização
---

# Atualização

1. Leia as [Novidades](./versioning) (o rodapé do chat e o release no GitHub) da versão de destino, principalmente se for um salto de MAJOR.
2. **Faça backup antes**: `docker compose exec app python -m app.backup backup`.
3. Baixe e reinicie:

```bash
docker compose pull          # ao usar a imagem publicada
docker compose up -d
curl http://127.0.0.1:8000/api/version
```

Ao construir localmente, use `git pull && docker compose up -d --build`.

4. Confira `GET /api/health` e os logs. As mudanças de esquema são aplicadas sozinhas na inicialização (só tabelas e índices novos; mudanças destrutivas seriam um release MAJOR com notas).

## Voltando atrás

Rode a tag anterior da imagem (`ghcr.io/ettorecsenatore/garimpo:0.3.0`) e, se os dados foram alterados de um jeito que a versão antiga não lê, restaure o backup do passo 2 (veja [Backup e restauração](./backup-restore)).

## Proxy reverso com Caddy

```caddyfile
garimpo.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

O Caddy obtém e renova o certificado HTTPS sozinho. Defina `TRUST_PROXY_HEADERS=true` só quando o proxy sobrescrever o `X-Forwarded-For` (o Caddy faz isso).
