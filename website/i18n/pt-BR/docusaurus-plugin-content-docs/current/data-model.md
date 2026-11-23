---
sidebar_position: 15
title: Modelo de dados
---

# Modelo de dados

SQLite (WAL) via SQLModel. Definido em `app/models.py`; o índice de texto completo fica em `app/search/fts.py`.

```mermaid
erDiagram
    CATEGORIES ||--o{ PRODUCTS : contem
    PRODUCTS ||--o{ PRODUCT_HISTORY : "muda ao longo do tempo"
    SCRAPE_RUNS {
      int id
      string run_type
      string status
    }
    PRODUCTS ||--|| PRODUCTS_FTS : "indexado por"
```

| Tabela | Guarda | Observações |
| --- | --- | --- |
| `categories` | Categorias da loja descobertas pelo sitemap | `id` é um CRC32 estável do caminho da categoria (a loja não expõe id numérico) |
| `products` | O estado atual de cada produto | preço, preço à vista, parcelas (JSON), tamanhos (JSON), estoque, imagens (JSON), breadcrumbs, marca, status, visualizações |
| `product_history` | Uma linha por **mudança real** de preço, preço à vista, disponibilidade ou status | Alimenta o gráfico de preço e a resposta de histórico do chat |
| `parse_failures` | As páginas mais recentes que falharam na leitura, com o início do HTML | Guardadas para depurar um redesenho da loja; só as `PARSE_FAILURE_SAMPLES_KEEP` (50) mais novas ficam |
| `scrape_runs` | Cada atualização completa, incremental ou individual | tipo, contagens de coletados, falhas e desaparecidos, status, erro |
| `products_fts` | Índice FTS5 do SQLite sobre nome, marca, breadcrumbs e slug | Ranking BM25; as descrições ficam de fora de propósito |

O status do produto é `active`, `out_of_stock` ou `disappeared`. Um produto é marcado como desaparecido quando a página dele retorna 404, **ou** quando some das listagens de `DISAPPEAR_AFTER_CRAWLS` (3) coletas completas seguidas (`products.missing_crawls` conta isso). Uma coleta que encontra menos de `DISAPPEAR_MIN_RATIO` (50 %) dos produtos conhecidos é tratada como quebrada e não muda nada, então uma queda do site nunca esvazia o catálogo. Um produto que reaparece volta a ficar ativo.

O esquema é gerenciado por migrações do [Alembic](./development#migrações-do-banco-de-dados): a `0001` é a base (o esquema da 0.4.0) e a `0002` adiciona `missing_crawls` e `parse_failures`.
