---
sidebar_position: 10
title: Desenvolvimento
---

# Desenvolvimento

## Estrutura

```text
app/            App FastAPI, scraper, busca, cliente Splunk
frontend/       Interface de chat em React + Vite + Tailwind
tests/          Suíte pytest (HTTP simulado com respx)
website/        Esta documentação (Docusaurus, inglês + português do Brasil)
.github/        CI, CodeQL, Dependabot, publicação da documentação
```

## Portões de qualidade

```bash
ruff check .                         # lint, incluindo regras de segurança (flake8-bandit)
python -m pytest tests -q            # 90 testes, sem rede
cd frontend && npx tsc --noEmit && npm run build
```

O CI roda as mesmas verificações, além de `pip-audit`, `npm audit` e um build Docker; o CodeQL analisa Python e TypeScript.

## Notas sobre testes

- `tests/conftest.py` define um banco temporário, desativa o agendador e limpa os limitadores de taxa entre os testes.
- Os testes do scraper usam HTMLs salvos em `tests/fixtures/`; os testes de Splunk e do proxy de imagens usam `respx`.
- Nunca adicione um teste que acesse o site real.

## Documentação

```bash
cd website
npm ci
npm start                          # inglês
npm start -- --locale pt-BR        # português do Brasil
npm run build
```

Mantenha os dois idiomas sincronizados: o inglês fica em `website/docs/`, o português em
`website/i18n/pt-BR/docusaurus-plugin-content-docs/current/`.
A documentação é publicada no GitHub Pages por `.github/workflows/docs.yml` a cada push na `main` que altere `website/`.

## Atualizando as capturas de tela

As capturas ficam em `website/static/img/screenshots/` e usam dados de demonstração (`python -m app.seed`),
para que nenhuma imagem de produto de terceiros seja publicada.
