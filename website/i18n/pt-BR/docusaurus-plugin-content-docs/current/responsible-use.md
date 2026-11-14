---
sidebar_position: 9
title: Uso responsável
---

# Uso responsável

Este software coleta dados de catálogo publicamente disponíveis em tivolli.com.br. É um projeto de portfólio e aprendizado.

:::warning Antes de rodar
Você precisa ter permissão para coletar dados do site e é responsável por cumprir os termos de uso,
o `robots.txt` e a legislação aplicável (incluindo a LGPD).
:::

## O que o projeto faz para ser um bom cidadão

- **Identifica-se** com um `User-Agent` descritivo; defina uma URL de contato que você controle.
- **Limita a taxa** a cerca de uma requisição por segundo em todo o processo, com jitter aleatório e espera exponencial em 429/5xx.
- **Respeita os caminhos proibidos**: `/tivadm43` e `/homologacao` são bloqueados no código, não apenas por convenção.
- **Fica no site**: apenas URLs `http(s)` do mesmo site são acessadas, e as listagens vêm do sitemap.
- **Não coleta dados pessoais**: apenas informações públicas de produto (nomes, preços, estoque, imagens).
- **Atualiza com moderação**: a tarefa incremental só busca de novo os produtos mais visualizados.

## O que você deve fazer

- Peça permissão ao dono do site, ou use um feed ou API oficial, se existir.
- Mantenha a taxa de requisições baixa; não reduza o jitter nem aumente `REQUESTS_PER_SECOND` sem acordo.
- Não republique imagens ou textos de produto comercialmente; aponte para a página de origem (`DISCLAIMER=true` ajuda).
- Trate os preços como indicativos: podem estar desatualizados.
