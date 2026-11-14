---
sidebar_position: 8
title: Segurança
---

# Segurança

Esta página lista as proteções embutidas no projeto e o que fazer ao implantá-lo.
Para reportar uma vulnerabilidade, use o formulário privado de advisories do repositório (veja `SECURITY.md`).

## Proteções embutidas

| Risco | Mitigação |
| --- | --- |
| **SSRF pelo proxy de imagens** | O host da requisição sempre vem de uma lista de permissão com correspondência exata (nunca do chamador), apenas https, sem IPs literais, cada redirecionamento é revalidado, limite de 5 MB, somente imagens raster (sem SVG/HTML). |
| **Acesso de admin** | Comparação de token em tempo constante, sem token padrão, endpoints desativados quando não configurado, a inicialização falha em produção com token fraco. |
| **Requisições entre sites** | CORS limitado às origens configuradas, sem credenciais. |
| **Endurecimento do navegador** | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e uma CSP restritiva nas respostas da API. |
| **XSS** | As respostas do chat são renderizadas como nós React, não como HTML; URLs de produto e de imagem precisam ser `http(s)`. |
| **Dados de origem maliciosos** | Links coletados precisam ser `http(s)` do mesmo site; `javascript:` e hosts externos são descartados. O sitemap é lido com entidades, DTDs e acesso à rede desativados. |
| **Abuso e DoS** | Limites de taxa por cliente, sessões de chat limitadas, limites de tamanho, um rastreador por vez, atualizações em andamento limitadas. |
| **Injeção** | ORM com parâmetros vinculados; o texto do usuário usado em `LIKE` é escapado, e as buscas de texto completo são remontadas só com palavras (entre aspas, como parâmetro), então operadores do FTS5 digitados pelo usuário não têm efeito. |
| **Segredos** | `.env`, bancos e buffers estão no `.gitignore`; secret scanning e push protection estão ativos no repositório. |
| **Cadeia de suprimentos** | Dependabot, `pip-audit` e `npm audit` no CI, CodeQL em cada pull request. |
| **Contêiner** | Sem root, sistema de arquivos somente leitura, sem capabilities, porta presa ao loopback. |

## Limites conhecidos

- O limite de taxa é **em memória do processo** e usa o endereço do cliente; rode uma única instância ou adicione um limite no proxy ao escalar.
- O proxy de imagens confia no DNS dos hostnames da lista de permissão.
- Não há autenticação de usuários; a API pública é somente leitura e sem autenticação por projeto.

## Reporte

Não abra issues públicas para vulnerabilidades. Use **Security → Report a vulnerability** no repositório do GitHub.
