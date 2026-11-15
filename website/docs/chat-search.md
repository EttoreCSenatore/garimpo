---
sidebar_position: 5
title: Chat search
---

# Chat search

`POST /api/chat` accepts a sentence and returns a conversational reply, the filters it applied and matching products.

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "tênis feminino número 38", "session_id": "demo-1"}'
```

## The guided flow

For footwear and clothing the bot asks for what is missing before searching, and remembers the answers for the session
(15 minutes, in memory).

![The assistant asks who the shoes are for](@site/static/img/screenshots/chat-guided.png)

1. **Gender**: *masculino*, *feminino*, *infantil* or *tanto faz* (don't care).
2. **Shoe size** (footwear only): a number such as `38`, or *tanto faz*.
3. **Results**: up to 24 products, best text match first (BM25 over name, brand, category and slug; a hit in the name counts most), then by popularity. If nothing matches, the size and then extra terms are relaxed, and the reply says so.

Neutral searches (balls, rackets, accessories) get no questions.

## What the parser understands

| Signal | Examples |
| --- | --- |
| Category | `corrida`, `running`, `futebol`, `chuteira`, `raquete`, `basquete`, `vôlei`, `camisa` |
| Brand | Nike, Adidas, Asics, Puma, New Balance, Yonex, ... |
| Price | `até 500`, `abaixo de 300`, `acima de 200`, `under 500`, `max 400` |
| Stock | `em estoque`, `disponível`, `in stock` |
| Gender / size | `feminino`, `masculino`, `infantil`, `nº 38`, `tamanho 42` |
| Free words | Anything else (for example a team name) narrows the search by name |

The parser is plain Python (regular expressions and dictionaries) in `app/search/intent_parser.py`, covered by unit tests.

## Follow-up tools

After a search, the chat can act on the products it just showed. Every answer is computed from the database (prices, sizes, recorded price history), never generated, and the follow-up buttons under the results send these messages:

| Say | What happens |
| --- | --- |
| `compare os 3 primeiros` | Side-by-side table: price, instalments, sizes, stock, and the cheapest one highlighted. |
| `qual o mais barato?` | The cheapest in-stock products among the previous results. |
| `mostre o histórico de preço` | Current, lowest and highest recorded price and the change since the first record. |

The product detail view also draws the price history as a line chart. Logic lives in `app/chat_tools.py`.

## On mobile

![Chat on a phone](@site/static/img/screenshots/chat-mobile.png)

## Safety

- Replies are rendered by React as text (only `**bold**` and line breaks are interpreted), never as raw HTML.
- Product links and image URLs are validated to be plain `http(s)`.
- The endpoint is rate limited per client and the session store is bounded.
