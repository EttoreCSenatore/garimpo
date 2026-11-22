---
sidebar_position: 10
title: Desenvolvimento
---

# Desenvolvimento

## Estrutura

```text
app/            App FastAPI, scraper, busca, eventos
frontend/       Interface de chat em React + Vite + Tailwind
tests/          Suíte pytest (HTTP simulado com respx)
website/        Esta documentação (Docusaurus, inglês + português do Brasil)
.github/        CI, CodeQL, Dependabot, publicação da documentação
```

## Portões de qualidade

```bash
ruff check . && ruff format --check .        # lint (com regras de segurança) e formatação
python -m pytest tests -q --cov=app          # sem rede, banco temporário; piso de cobertura no pyproject.toml
cd frontend && npx tsc --noEmit && npm run build
```

O CI roda as mesmas verificações, além de `pip-audit`, `npm audit`, a checagem das travas e um build Docker; o CodeQL analisa Python e TypeScript.

## Dependências e cadeia de suprimentos

- As dependências diretas ficam em `requirements.in` (execução) e `requirements-dev.in` (ferramentas). `requirements.txt` e `requirements-dev.txt` são arquivos **travados com hashes**, gerados por `deploy/lock.sh` dentro do mesmo Python da imagem (precisa de Docker). O CI roda `deploy/lock.sh --check` e falha quando uma trava está desatualizada; as instalações usam `--require-hashes`.
- As GitHub Actions são fixadas em um SHA de commit com a tag em comentário, e a imagem base do Docker em um digest; o Dependabot atualiza os dois.
- O Dependabot espera 7 dias após um release antes de propor uma atualização de versão (um pacote comprometido costuma ser retirado em poucos dias); as atualizações de segurança não esperam.
- A cobertura de testes tem um piso (`fail_under` no `pyproject.toml`, hoje 85 % contra cerca de 88 % medidos) que deve subir para 90 %.

## Notas sobre testes

- `tests/conftest.py` define um banco temporário, desativa o agendador e limpa os limitadores de taxa entre os testes.
- Os testes do scraper usam HTMLs salvos em `tests/fixtures/`; os testes do proxy de imagens usam `respx`.
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

## Canário do scraper

Um workflow semanal (`.github/workflows/canary.yml`, também executável com `python -m app.canary`) faz cerca de quatro requisições educadas à loja real e confere se categorias, links de produto, nome, preço, imagens e tamanhos ainda são lidos. Se a loja mudar o HTML, ele falha em poucos dias, em vez de uma coleta devolver vazio em silêncio.
