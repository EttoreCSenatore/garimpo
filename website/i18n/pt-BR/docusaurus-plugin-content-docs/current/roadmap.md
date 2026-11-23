---
sidebar_position: 11
title: Roadmap
---

# Roadmap

O Garimpo funciona de ponta a ponta: um scraper educado, uma API, busca em texto completo e um chat com acompanhamentos. Este roadmap trata de torná-lo **confiável para operar, fácil de lançar e agradável de mostrar**. Boa parte vem do [Kaladrius](https://github.com/facchini-miguel/kaladrius), um sistema open source de gestão de clínicas (Django, Apache-2.0, mais de 70 versões) cujos hábitos de engenharia são um bom modelo.

## O que o Kaladrius faz e podemos aprender

Produto diferente, mesma disciplina. Estas são as práticas que vale adaptar e o que deixamos de fora.

| Área | Kaladrius | Garimpo hoje | Veredito |
| --- | --- | --- | --- |
| **Cadeia de suprimentos** | Actions de terceiros fixadas por SHA; dependências travadas com hashes (`pip-compile`); Dependabot com espera de 7 dias; imagens Docker fixadas por digest | Actions por tag; requirements com `>=`; Dependabot agrupado, sem espera | **Adotar** (M1) |
| **Portões do CI** | Lint e verificação de formato, checagens do Django, testes com piso de 90 % de cobertura, build da documentação, instala os pacotes em distros limpas | Lint, testes, build do frontend, build do docker, CodeQL, build da documentação; sem piso de cobertura | **Adotar** piso de cobertura e verificação de formato (M1) |
| **Segurança de migrações** | Um workflow mostra o SQL de cada migração no PR e testa o rollback | Esquema por `create_all` e índices idempotentes, sem migrações | **Adotar** com o Alembic (M4) |
| **Versões** | SemVer, um `releases.yaml` alimenta a página "Novidades", a API e os GitHub Releases; imagem publicada no ghcr.io | Sem tags nem releases; sem versão na interface | **Adotar** (M2) |
| **Backups** | Dump diário, retenção, teste semanal automático de restauração em banco descartável, aviso no app se o backup atrasa | Nada documentado para o arquivo SQLite | **Adotar** (M3) |
| **Monitoramento** | Pings do Healthchecks.io por tarefa (sistema, backup, restauração, atualização, disco, certificado): avisa quando um sinal falha ou deixa de chegar; métricas Prometheus por arquivo de texto; `/api/v1/version` e `/health` | Só `/api/health` | **Adotar** (M3); um sinal após cada coleta combina perfeitamente com o nosso agendador |
| **Decisões** | Registro numerado com data, motivo, status e links de substituição | As decisões ficam no texto dos PRs | **Adotar** um registro curto (M2) |
| **Arquivos da comunidade** | CODEOWNERS, CONTRIBUTING, Código de Conduta, SECURITY com fluxo de advisories | Só SECURITY | **Adotar** (M1) |
| **Demo** | Servidor de demonstração público que reinicia toda noite, com logins por perfil | Script de demo local | **Adotar** a ideia do reset quando houver hospedagem (M6) |
| **Estrutura da documentação** | Instalar / operar / manual / projeto (visão, modelo de dados, glossário, decisões) | Bom guia em en e pt-BR, sem páginas de operação nem de decisões | **Adotar** seções de operação e projeto (M3, M2) |
| Isolamento multi-clínica, auditoria de pessoas, financeiro, perfis de acesso | Essencial para um sistema de clínica | Um catálogo, sem contas de usuário | **Desnecessário** |
| Interface e docs em três idiomas (en, pt-BR, es) | Sim | en e pt-BR | **Manter dois idiomas** |
| Pacotes Linux (.deb/.rpm), repositório apt | Sim, para quem instala sem ser técnico | Imagem Docker | **Pular**: nosso público usa contêineres |
| App mobile, stack Django | Sim | Chat web em React | **Não se aplica** |

## Marcos

Cada marco é um punhado de PRs pequenos, em ordem de valor pelo esforço.

### M1: Cadeia de suprimentos e CI (concluído)

- Fixar toda Action de terceiros em um SHA de commit com a tag em comentário; o Dependabot atualiza os dois.
- Travar as dependências Python com hashes (`pip-compile --generate-hashes`, trava separada para desenvolvimento) e falhar o CI quando a trava estiver desatualizada.
- `cooldown` de 7 dias do Dependabot nas atualizações de versão; as de segurança continuam imediatas.
- Medir a cobertura de testes, definir um piso (começar no valor atual e subir para 90 %) e adicionar `ruff format --check`.
- `persist-credentials: false` em todo checkout; manter as permissões do CI em `contents: read`.
- Adicionar `CODEOWNERS`, `CONTRIBUTING.md` e um Código de Conduta.
- Fixar a imagem base do Docker por digest.

### M2: Versões, releases e decisões (concluído)

- Adotar SemVer a partir de `0.1.0`; versão exposta em `GET /api/version` e no rodapé da interface.
- Um `releases.yaml` (ou `CHANGELOG`) como fonte dos GitHub Releases e de uma página "Novidades" na documentação (en + pt-BR).
- Workflow de release com tag: construir e publicar a imagem no ghcr.io com proveniência e SBOM.
- Abrir um registro numerado de decisões na documentação (SQLite primeiro, chat por regras, por que sem LLM, coleta educada, sem Splunk) com data, motivo e status.
- Páginas de visão, modelo de dados e glossário em uma seção "Projeto".

### M3: Operar de verdade (concluído)

- **Backups:** backup online diário do SQLite (`.backup`), retenção e um teste semanal de restauração em um arquivo descartável. Registrar o último backup e avisar quando passar de 26 horas.
- **Sinais de vida:** pings opcionais no estilo Healthchecks.io (URL no `.env`) após cada coleta completa, coleta incremental, backup e canário; o silêncio indica que algo parou. É a forma mais barata de saber que o scraper morreu.
- **Métricas:** um endpoint `/metrics` ou arquivo de texto (duração da coleta, falhas de leitura, produtos coletados, tamanho da fila, horário do último sucesso).
- **Frescor na interface:** avisar os visitantes quando o catálogo passar de um limite de idade.
- **Documentação:** seção de Operação: instalar, atualizar, backup e restauração, monitoramento, logs.
- Implantação de referência: compose com proxy reverso TLS (Caddy) e um timer do systemd para os backups.

### M4: Dados e correção (quase concluído)

Feito: migrações com Alembic e relatório no PR, detecção de desaparecimento pelas coletas, resiliência do parser (amostras de falha e alerta de pico), retenção. Adiado (decisão 022): opção PostgreSQL com limites no Redis e sinônimos aprendidos do catálogo.

- **Migrações com Alembic** no lugar do `create_all`; um workflow nos PRs que mostra o SQL de cada migração e testa subir e descer em uma cópia.
- **Detectar produtos que sumiram nas coletas:** marcar como ausente após N coletas completas seguidas sem o produto, não só em um 404.
- **Resiliência do parser:** manter o canário, alertar quando a taxa de falhas subir e guardar uma amostra do HTML que falhou para depuração.
- **Retenção:** limpar coletas antigas e compactar o histórico, como o Kaladrius faz com a auditoria.
- **Opção PostgreSQL** com as mesmas migrações, para quem quiser mais de uma instância; limites de taxa e sessões do chat vão para o Redis só se isso acontecer.
- Relevância mais inteligente: sinônimos aprendidos do catálogo.

### M5: Recursos para quem compra (concluído)

Feito: Explorar (filtros e ordenação), Ofertas, avisos de queda de preço e volta ao estoque (ntfy e webhooks de lista permitida, por tamanho). Não embutidos: Telegram e e-mail (decisão 024).

- Filtros e ordenação ao lado do chat (tamanho em estoque, marca, faixa de preço, categoria).
- **Página de ofertas:** maiores quedas em relação ao histórico do próprio produto, com "menor preço em 90 dias".
- **Lista de acompanhamento e alertas de queda de preço** por ntfy, Telegram, webhook ou e-mail (o mesmo desenho de canais do Atalaia).
- Disponibilidade por tamanho e alertas de volta ao estoque.

### M6: Mostrar o projeto (demo e portfólio)

- Demo hospedada com dados de demonstração e reinício noturno para não se desviar; a escolha do servidor ainda está em aberto.
- Notas de arquitetura e um pequeno vídeo no README.
- Imagens reais de produtos somente se a loja der permissão.

### M7: Chat com IA opcional (decisão pendente)

- Um modo com Claude atrás de uma configuração de chave de API, com uso de ferramentas limitado às mesmas funções fundamentadas de hoje (busca, comparação, histórico). Exige proteção contra injeção de prompt vinda do texto coletado e um orçamento de custo por mensagem. Desligado por padrão.

## Como vamos trabalhar

- Toda mudança por PR com verificações verdes; documentação atualizada em inglês e português no mesmo PR.
- Cada marco termina com um release com tag, depois que o M2 existir.
- Escolhas não óbvias vão para o registro de decisões.
