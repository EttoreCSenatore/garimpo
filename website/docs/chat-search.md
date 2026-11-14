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
3. **Results**: up to 24 products ordered by popularity. If nothing matches, the size and then extra terms are relaxed, and the reply says so.

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

## On mobile

![Chat on a phone](@site/static/img/screenshots/chat-mobile.png)

## Safety

- Replies are rendered by React as text (only `**bold**` and line breaks are interpreted), never as raw HTML.
- Product links and image URLs are validated to be plain `http(s)`.
- The endpoint is rate limited per client and the session store is bounded.
