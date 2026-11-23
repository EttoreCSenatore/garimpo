---
sidebar_position: 12
title: Versioning and releases
---

# Versioning and releases

Garimpo follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

| Part | Goes up when | Example |
| --- | --- | --- |
| **MAJOR** | A breaking change (API shape, configuration or data that older installs cannot use) | 1.4.2 → **2.0.0** |
| **MINOR** | A new feature or a relevant compatible improvement | 1.4.2 → **1.5.0** |
| **PATCH** | A bug fix or a small adjustment | 1.4.2 → **1.4.3** |

While the version is `0.x.y` the API may still change between minors.

## One source for the history: `app/releases.yaml`

Newest entry first, with every text in English (`en`) and Portuguese (`pt-br`). It feeds:

- the **What's new** window in the chat (footer link) and `GET /api/releases?lang=pt-br`;
- the GitHub Release notes (`python scripts/release_notes.py X.Y.Z`);
- the version in `GET /api/version`, which any uptime monitor can poll without login.

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

Write for the user, not the developer, in a line or two. Security fixes say that something was fixed, not how. Tests require both languages, valid kinds, SemVer order and that the newest entry equals `app/version.py`.

## How to release

1. Add the entry to `app/releases.yaml` and bump `app/version.py` to the same version.
2. Merge through a pull request with green checks.
3. Tag the merge commit and push the tag:

```bash
git tag v0.4.0 && git push origin v0.4.0
```

The **Release** workflow checks that the tag, `app/version.py` and the newest entry agree, then builds the image and publishes it to `ghcr.io/ettorecsenatore/garimpo` (tags `0.4.0`, `0.4` and `latest`) with build provenance and an SBOM, and creates the GitHub Release from the notes.

```bash
docker pull ghcr.io/ettorecsenatore/garimpo:0.4.0
```
