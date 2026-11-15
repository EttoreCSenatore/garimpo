---
sidebar_position: 11
title: Roteiro
---

# Roteiro e notas de revisão

Uma revisão do código original levou às correções de segurança e confiabilidade já incorporadas.
Estas são as ideias restantes, aproximadamente por valor.

## Correção

- **Detectar produtos que sumiram pelas coletas**: hoje um produto vira `disappeared` apenas com um 404. Compare cada coleta completa com o catálogo e marque os ausentes após N ausências consecutivas.
- **Resiliência do parser**: ler preços de dados estruturados (JSON-LD / meta tags) antes de seletores CSS e regex, e alertar quando a taxa de falhas de leitura disparar.
- **Relevância mais inteligente**: ordenar os resultados do chat por pontuação de texto (correspondência no nome) antes da popularidade, e adicionar sinônimos aprendidos do catálogo.

## Desempenho e escala

- **Acesso assíncrono ao banco**: as chamadas ao SQLite rodam de forma síncrona dentro de handlers assíncronos; mova consultas pesadas para um pool de threads ou adote um driver assíncrono.
- **Opção PostgreSQL**: caminho de migração documentado e migrações com Alembic (hoje `create_all` mais índices idempotentes).
- **Limites compartilhados**: mover limites e sessões de chat para o Redis se for necessário mais de uma instância.

## Produto

- **Alertas de queda de preço** usando a tabela de histórico.
- **Interface com consciência de categoria**: filtros e ordenação ao lado do chat.
- **Imagens reais nas demonstrações** quando houver permissão.

## Operações

- **Métricas**: endpoint Prometheus (duração das coletas, falhas de leitura, tamanho da fila).
- **Fixar e travar as dependências Python** (`pip-compile`) para imagens totalmente reproduzíveis.
- **Automação de releases**: versões com tag, imagem de contêiner publicada e SBOM.
