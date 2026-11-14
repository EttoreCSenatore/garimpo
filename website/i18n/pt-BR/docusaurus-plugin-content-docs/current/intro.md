---
slug: /
sidebar_position: 1
title: Tivolli Sports
---

# Tivolli Sports

**Tivolli Sports** é um coletor de catálogo (scraper), uma API REST e uma busca conversacional para um e-commerce brasileiro de artigos esportivos (tivolli.com.br).
Ele mantém uma cópia local do catálogo, atualizada quase em tempo real, e permite buscar em português ou inglês:
*"tênis feminino número 38"*, *"chuteiras nike até 500"*, *"camisa do flamengo"*.

![Busca conversacional com cartões de produto](@site/static/img/screenshots/chat-results.png)

:::info Dados de demonstração
As capturas de tela desta documentação usam produtos genéricos de demonstração (`python -m app.seed`), e não o catálogo nem as imagens reais da loja.
:::

## O que vem no projeto

| Parte | O que faz |
| --- | --- |
| **Scraper** | Descobre categorias pelo `sitemap.xml` e percorre listagens e páginas de produto a ~1 requisição por segundo, com jitter e espera progressiva. |
| **API REST** | Serviço FastAPI com paginação por cursor, filtros, histórico de preços e documentação OpenAPI. |
| **Busca por chat** | Um interpretador de intenção baseado em regras (sem LLM, sem chaves de API) transforma uma frase em filtros e pergunta gênero e número do calçado quando necessário. |
| **Frontend** | Interface de chat em React + TypeScript + Tailwind que exibe os produtos como cartões. |
| **Observabilidade** | Logs estruturados e envio ao Splunk HEC, com buffer em disco quando o Splunk está indisponível. |

## Destaques

- Educado por padrão: orçamento de requisições global ao processo, caminhos proibidos pelo `robots.txt` bloqueados no código, apenas URLs do mesmo site.
- Padrões seguros: proxy de imagens à prova de SSRF, token de admin com comparação em tempo constante, CORS restrito, limites de taxa, contêiner sem root.
- Testado: uma suíte pytest com HTTP simulado, sem rede e sem banco real, executada pelo CI em cada pull request.
- Documentado em inglês e em português do Brasil.

## Próximos passos

- Primeira vez aqui? Comece por [Primeiros passos](getting-started.md).
- Quer entender como as peças se encaixam? Leia a [Arquitetura](architecture.md).
- Vai rodar de verdade? Veja [Implantação](deployment.md), [Segurança](security.md) e [Uso responsável](responsible-use.md).
