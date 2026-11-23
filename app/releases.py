"""Release history loaded from app/releases.yaml (newest first)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.version import __version__

RELEASES_FILE = Path(__file__).with_name("releases.yaml")
KINDS = {"new", "improvement", "fix", "security"}
LANGS = ("en", "pt-br")


@lru_cache(maxsize=1)
def load_releases() -> list[dict]:
    with RELEASES_FILE.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or []


def current_release() -> dict:
    for release in load_releases():
        if release["version"] == __version__:
            return release
    return {"version": __version__, "date": None}


def localized(lang: str) -> list[dict]:
    """The releases with every text reduced to one language (falls back to English)."""
    lang = lang.lower()
    if lang not in LANGS:
        lang = "en"

    def pick(texts: dict) -> str:
        return texts.get(lang) or texts["en"]

    return [
        {
            "version": r["version"],
            "date": str(r["date"]),
            "title": pick(r["title"]),
            "items": [{"kind": i["kind"], "text": pick(i["text"])} for i in r["items"]],
        }
        for r in load_releases()
    ]
