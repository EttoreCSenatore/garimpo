---
sidebar_position: 4
title: API REST
---

# API REST

A documentação interativa é servida pela própria API em `/docs` (Swagger UI) e `/openapi.json`.

![Swagger UI](@site/static/img/screenshots/api-docs.png)

## Endpoints públicos

| Método | Caminho | Descrição |
| --- | --- | --- |
| GET | `/api/health` (também `/` e `/api/`) | Disponibilidade e horário da última atualização concluída. |
| GET | `/products` | Lista produtos. Filtros: `category_id`, `brand`, `min_price`, `max_price`, `available`, `q`. Paginação por cursor com `cursor` e `limit` (1–200). |
| GET | `/products/{id}` | Um produto. Incrementa o contador de visualizações e agenda atualização se os dados têm mais de 5 minutos. |
| GET | `/products/{id}/history` | Histórico de preço e disponibilidade. |
| GET | `/categories` | Categorias com contagem de produtos. |
| GET | `/stats` | Totais e taxa de sucesso das coletas nas últimas 24 h. |
| POST | `/api/chat` | Busca conversacional (veja [Busca por chat](chat-search.md)). |
| GET | `/api/image-proxy?url=` | Proxy para imagens de produto em lista de permissão. |

Exemplo:

```bash
curl "http://127.0.0.1:8000/products?brand=Nike&max_price=500&available=true&limit=10"
```

```json
{
  "items": [{ "id": 123, "name": "Tênis Nike ...", "price": "399.90", "available": true }],
  "next_cursor": "123",
  "total": 42
}
```

`q` é uma busca de texto completo (SQLite FTS5) em nome, marca, breadcrumbs da categoria e slug: acentos e maiúsculas são ignorados, as palavras podem vir em qualquer ordem e cada palavra também vale como prefixo (`bol` encontra *bola* e *bolas*). Todas as palavras precisam corresponder. Em bancos sem FTS5, volta a comparar o nome de forma literal. As respostas trazem `Cache-Control: public, max-age=60`.

## Endpoints de administração

Exigem o cabeçalho `X-Admin-Token`. Ficam **desativados quando `ADMIN_TOKEN` está vazio**.

| Método | Caminho | Descrição |
| --- | --- | --- |
| POST | `/admin/refresh` | Inicia uma atualização completa (ignorada se já houver uma em andamento). |
| POST | `/admin/refresh/{id}` | Atualiza um produto. |
| GET | `/admin/queue` | Workers ativos, atualizações em andamento e número de sessões de chat. |

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://127.0.0.1:8000/admin/refresh
```

## Compras e avisos

| Método | Caminho | Descrição |
| --- | --- | --- |
| GET | `/api/catalog` | Filtra (`q`, `brand`, `category_id`, `min_price`, `max_price`, `size`, `in_stock`), ordena (`sort`) e pagina (`offset`, `limit`) o catálogo. |
| GET | `/api/facets` | Marcas, tamanhos em estoque, categorias e a faixa de preço, para montar filtros. |
| GET | `/api/deals` | Produtos no menor preço registrado dos últimos `days` dias, maior queda primeiro. |
| GET | `/api/alerts/config` | Se os avisos estão ligados e quais canais existem. |
| POST / GET / DELETE | `/api/watches` | Gerencia avisos (cabeçalho `X-Watcher-Id`). Veja [Explorar, ofertas e avisos](./shopping). |

## Erros e limites

- `401` token de admin inválido ou ausente, `422` parâmetros inválidos, `429` limite de taxa excedido (com `Retry-After`).
- Mensagens de chat têm no máximo 500 caracteres; ids de sessão devem seguir `[A-Za-z0-9_-]{1,64}`.
- Com `DISCLAIMER=true`, os preços são marcados como indicativos e cada produto ganha um `source_url`.
