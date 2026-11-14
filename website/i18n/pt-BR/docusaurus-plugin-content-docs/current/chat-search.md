---
sidebar_position: 5
title: Busca por chat
---

# Busca por chat

`POST /api/chat` recebe uma frase e devolve uma resposta conversacional, os filtros aplicados e os produtos encontrados.

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "tênis feminino número 38", "session_id": "demo-1"}'
```

## O fluxo guiado

Para calçados e vestuário, o assistente pergunta o que falta antes de pesquisar e lembra as respostas durante a sessão
(15 minutos, em memória).

![O assistente pergunta para quem são os tênis](@site/static/img/screenshots/chat-guided.png)

1. **Gênero**: *masculino*, *feminino*, *infantil* ou *tanto faz*.
2. **Número do calçado** (apenas calçados): um número como `38`, ou *tanto faz*.
3. **Resultados**: até 24 produtos, a melhor correspondência de texto primeiro (BM25 em nome, marca, categoria e slug; acertar o nome vale mais), depois por popularidade. Se nada corresponder, o número e depois os termos extras são relaxados, e a resposta avisa.

Buscas neutras (bolas, raquetes, acessórios) não recebem perguntas.

## O que o interpretador entende

| Sinal | Exemplos |
| --- | --- |
| Categoria | `corrida`, `running`, `futebol`, `chuteira`, `raquete`, `basquete`, `vôlei`, `camisa` |
| Marca | Nike, Adidas, Asics, Puma, New Balance, Yonex, ... |
| Preço | `até 500`, `abaixo de 300`, `acima de 200`, `under 500`, `max 400` |
| Estoque | `em estoque`, `disponível`, `in stock` |
| Gênero / número | `feminino`, `masculino`, `infantil`, `nº 38`, `tamanho 42` |
| Palavras livres | Qualquer outra palavra (por exemplo, o nome de um time) restringe a busca pelo nome |

O interpretador é Python puro (expressões regulares e dicionários) em `app/search/intent_parser.py`, coberto por testes unitários.

## No celular

![Chat no celular](@site/static/img/screenshots/chat-mobile.png)

## Segurança

- As respostas são renderizadas pelo React como texto (apenas `**negrito**` e quebras de linha são interpretados), nunca como HTML bruto.
- Links de produto e URLs de imagem são validados como `http(s)` simples.
- O endpoint tem limite de taxa por cliente e o armazenamento de sessões é limitado.
