---
sidebar_position: 12
title: Versões e releases
---

# Versões e releases

O Garimpo segue o [Versionamento Semântico](https://semver.org/lang/pt-BR/): `MAJOR.MINOR.PATCH`.

| Parte | Sobe quando | Exemplo |
| --- | --- | --- |
| **MAJOR** | Há uma mudança que quebra compatibilidade (formato da API, configuração ou dados que instalações antigas não usam) | 1.4.2 → **2.0.0** |
| **MINOR** | Há um recurso novo ou uma melhoria relevante e compatível | 1.4.2 → **1.5.0** |
| **PATCH** | Há uma correção de bug ou um pequeno ajuste | 1.4.2 → **1.4.3** |

Enquanto a versão for `0.x.y`, a API ainda pode mudar entre minors.

## Uma fonte para o histórico: `app/releases.yaml`

Entrada mais nova primeiro, com todos os textos em inglês (`en`) e português (`pt-br`). Ele alimenta:

- a janela **Novidades** do chat (link no rodapé) e `GET /api/releases?lang=pt-br`;
- as notas dos GitHub Releases (`python scripts/release_notes.py X.Y.Z`);
- a versão em `GET /api/version`, que qualquer monitor de disponibilidade consulta sem login.

```yaml
- version: 0.4.0
  date: 2026-12-01
  title: {en: Price alerts, pt-br: Alertas de preço}
  items:
    - kind: new            # new | improvement | fix | security
      text:
        en: Get a notification when a watched product drops in price.
        pt-br: Receba um aviso quando um produto acompanhado baixar de preço.
```

Escreva para o usuário, não para quem desenvolve, em uma ou duas linhas. Correções de segurança dizem que algo foi corrigido, não como. Os testes exigem os dois idiomas, tipos válidos, ordem SemVer e que a entrada mais nova seja igual a `app/version.py`.

## Como lançar uma versão

1. Adicione a entrada em `app/releases.yaml` e suba `app/version.py` para a mesma versão.
2. Faça o merge por pull request com as verificações verdes.
3. Crie a tag no commit do merge e envie:

```bash
git tag v0.4.0 && git push origin v0.4.0
```

O workflow **Release** confere se a tag, `app/version.py` e a entrada mais nova coincidem, constrói a imagem e a publica em `ghcr.io/ettorecsenatore/garimpo` (tags `0.4.0`, `0.4` e `latest`) com proveniência de build e SBOM, e cria o GitHub Release a partir das notas.

```bash
docker pull ghcr.io/ettorecsenatore/garimpo:0.4.0
```
