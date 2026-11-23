---
sidebar_position: 13
title: Registro de decisões
---

# Registro de decisões

Cada linha é uma decisão com data e motivo. Quando uma decisão muda, a linha antiga é marcada como substituída e uma nova é adicionada, preservando o histórico.

| # | Data | Decisão | Motivo | Status |
| --- | --- | --- | --- | --- |
| 001 | 2026-11-14 | Python, FastAPI e SQLModel para a API e o scraper | Uma linguagem para coleta, API e testes; documentação OpenAPI automática | Aceita |
| 002 | 2026-11-14 | SQLite (WAL) como banco de dados | Sem configuração, um arquivo para backup, suficiente para um catálogo; o Postgres segue no roadmap | Aceita |
| 003 | 2026-11-14 | Chat por regras, sem LLM | Toda resposta é calculada a partir do banco, sem chave de API, custo nem preços inventados | Aceita (um modo com IA opcional está em estudo, M7) |
| 004 | 2026-11-14 | Um orçamento de requisições para o processo todo (cerca de 1 req/s com variação) | Tarefas paralelas nunca devem multiplicar a carga sobre a loja | Aceita |
| 005 | 2026-11-14 | Espelhar o robots.txt no código (caminhos e parâmetros) | URLs bloqueadas falham antes de qualquer requisição | Aceita |
| 006 | 2026-11-14 | Proxy de imagens com lista exata de hosts, sem IPs, limite de tamanho e redirecionamentos revalidados | Evita SSRF pelo proxy | Aceita |
| 007 | 2026-11-14 | Renomear o projeto para Garimpo; a loja é apenas a fonte dos dados | O projeto não deve levar o nome da loja | Aceita |
| 008 | 2026-11-14 | Ler as páginas Magento da loja pelo JSON-LD e pela configuração embutida, não por seletores CSS | Dados estruturados sobrevivem melhor a redesenhos que HTML e expressões regulares | Aceita |
| 009 | 2026-11-14 | Índice de texto completo (FTS5) só em nome, marca, breadcrumbs e slug; descrições fora | As descrições geravam resultados falsos | Aceita |
| 010 | 2026-11-14 | Gravar o histórico de preços só quando um campo monitorado muda | Tabela pequena, cada linha é uma mudança real | Aceita |
| 011 | 2026-11-14 | Repositório público sob licença MIT; `main` só por pull requests com verificações obrigatórias | Aberto por padrão, nada chega à `main` sem revisão ou com falha | Aceita |
| 012 | 2026-11-14 | Documentação em inglês e português do Brasil, sempre em sincronia | Dois públicos, um projeto | Aceita |
| 013 | 2026-11-22 | Remover o Splunk; emitir eventos JSON estruturados pelo structlog | O plano gratuito acabou; JSON no stdout serve a qualquer coletor de logs | Aceita (substitui o desenho anterior com Splunk HEC) |
| 014 | 2026-11-22 | Acompanhamentos do chat (comparar, mais barato, histórico) agem sobre os resultados anteriores e são calculados a partir do banco | Conversa sem geração de texto, respostas verificáveis | Aceita |
| 015 | 2026-11-22 | Canário semanal contra a loja | A migração para Magento quebrou o scraper em silêncio; uma checagem barata percebe mudanças de HTML cedo | Aceita |
| 016 | 2026-11-22 | Dependências com hashes travados, actions fixadas por SHA, imagem fixada por digest e espera de 7 dias no Dependabot | Um pacote comprometido ou uma tag movida não pode mudar o que roda | Aceita |
| 017 | 2026-11-22 | SemVer a partir de 0.1.0; `app/releases.yaml` como fonte única do histórico; imagens publicadas no ghcr.io com proveniência e SBOM | Uma verdade para Novidades, API e GitHub Releases | Aceita |
| 018 | 2026-11-22 | Migrações do Alembic substituem o `create_all`; bancos existentes são adotados marcando uma base | Mudanças de esquema precisam de histórico e de caminho de volta; as pessoas já têm um `garimpo.db` | Aceita |
| 019 | 2026-11-22 | Marcar um produto como desaparecido após N coletas completas seguidas sem ele, ignorando coletas que encontram menos da metade dos produtos conhecidos | Um produto pode deixar de ser listado sem um 404; uma queda do site nunca deve esvaziar o catálogo | Aceita |
| 020 | 2026-11-22 | Guardar amostras de páginas que falham na leitura e alertar em picos de falha | Um redesenho da loja deve ser depurável em minutos, não descoberto por dados vazios | Aceita |
| 021 | 2026-11-22 | Apagar coletas após 90 dias; manter o histórico de preços para sempre por padrão | As coletas são ruído operacional; o histórico é o valor do produto | Aceita |
| 022 | 2026-11-22 | Suporte a Postgres, limites com Redis e sinônimos aprendidos do catálogo ficam adiados | Desnecessários para uma instância; as migrações são escritas de forma portável, então o Postgres continua possível | Adiada |
| 023 | 2026-11-22 | Avisos sem contas de usuário: um id aleatório do navegador é a chave | Sem senhas nem e-mails para guardar ou vazar; o custo é que limpar os dados do navegador os esquece | Aceita |
| 024 | 2026-11-22 | Entrega de avisos só por ntfy e webhooks de uma lista permitida; Telegram e e-mail não vêm embutidos | Ambos exigem credenciais de quem opera; os webhooks chegam a eles por uma ponte, e a lista de hosts exatos evita SSRF | Aceita |
| 025 | 2026-11-22 | Uma "oferta" é uma queda real registrada até o menor preço da janela, nunca o "de/por" da loja | As alegações da loja não são verificáveis; o nosso histórico é | Aceita |
