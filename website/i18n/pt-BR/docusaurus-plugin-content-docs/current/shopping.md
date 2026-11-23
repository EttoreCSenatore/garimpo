---
sidebar_position: 6
title: Explorar, ofertas e avisos
---

# Explorar, ofertas e avisos

Além do chat, o app web tem mais duas abas e uma caixa de aviso na tela do produto.

## Explorar

![Aba Explorar com filtros](@site/static/img/screenshots/explore.png)

Filtre por texto, marca, tamanho **em estoque**, faixa de preço e se esconde produtos esgotados; ordene por relevância, preço, popularidade, novidade ou nome; carregue mais no fim da página. Os tamanhos oferecidos são os que existem em estoque hoje. API: `GET /api/catalog` e `GET /api/facets`.

## Ofertas

![Aba Ofertas](@site/static/img/screenshots/deals.png)

Uma oferta aqui é uma **queda real registrada pelo Garimpo**: o produto está em estoque, o preço atual é o menor dos últimos 90 dias e está pelo menos 5 % abaixo do maior preço visto nessa janela. O "de/por" da própria loja não é usado. O chat responde a *ofertas* do mesmo jeito. API: `GET /api/deals?days=90&min_discount=5`.

## Avisos

![Caixa de aviso com preço-alvo](@site/static/img/screenshots/watch.png)

Na tela de um produto, **Avisar-me** cria um acompanhamento: uma notificação quando o preço baixar, quando um tamanho voltar ao estoque (escolha o tamanho) ou quando o preço chegar a um valor-alvo. Nada é enviado quando o preço sobe, e cada queda ou volta ao estoque é avisada uma vez.

**Não há contas.** O navegador guarda um id aleatório (`X-Watcher-Id`, de 22 a 64 caracteres) que é a única chave dos seus avisos, então limpar os dados do navegador os esquece. Canais de entrega:

- **ntfy** (padrão): você escolhe um nome de tópico (o app sugere um aleatório), instala o app [ntfy](https://ntfy.sh) e assina o tópico. Quem souber o nome do tópico lê os avisos, então mantenha-o privado.
- **Webhook**: só para os hosts que a pessoa que opera o servidor listar em `ALERTS_WEBHOOK_HOSTS` (por exemplo `hooks.slack.com`); o corpo traz `text` (Slack) e `content` (Discord), além de campos JSON para o seu próprio endpoint.

Telegram e e-mail não vêm embutidos: precisam de credenciais da pessoa que opera. Um webhook para uma ponte cobre isso por enquanto.

### Ligando (quem opera)

Os avisos vêm **desligados por padrão** porque fazem requisições de saída a partir do seu servidor.

```bash
ALERTS_ENABLED=true
ALERTS_NTFY_SERVER=https://ntfy.sh          # ou o seu próprio ntfy
ALERTS_WEBHOOK_HOSTS=hooks.slack.com        # vazio: webhooks desativados
```

| Endpoint | O que faz |
| --- | --- |
| `GET /api/alerts/config` | Se os avisos estão ligados e quais canais existem. |
| `POST /api/watches` | Cria ou atualiza um aviso (`product_id`, `size` e `target_price` opcionais, `channel`, `destination`). Exige `X-Watcher-Id`. |
| `GET /api/watches` | Os avisos de quem chama; os destinos vêm mascarados (`gar…`). |
| `DELETE /api/watches/{id}` | Remove um aviso de quem chama. |

### Privacidade e segurança

- Um aviso guarda o tópico do ntfy ou a URL do webhook que a pessoa digitou, o produto, o tamanho e o preço-alvo. Nenhum nome, e-mail ou IP é guardado. A API nunca devolve um destino completo.
- Para apagar tudo de uma pessoa, apague os avisos dela (`DELETE /api/watches/{id}`) ou as linhas da tabela `watches`.
- O servidor contata **somente** o `ALERTS_NTFY_SERVER` e os hosts HTTPS exatos que você permitir: ninguém consegue apontá-lo para um endereço interno (SSRF). Os hosts de webhook são conferidos de novo no envio.
- A criação de avisos tem limite de taxa (`WATCH_RATE_LIMIT_PER_MINUTE`) e teto por navegador (`ALERTS_MAX_WATCHES_PER_WATCHER`, 20).
- Uma entrega que falha é tentada de novo na próxima coleta daquele produto, em vez de se perder.
