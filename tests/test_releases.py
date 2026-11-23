import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.releases import KINDS, LANGS, load_releases, localized
from app.version import __version__

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def test_newest_release_matches_the_version_constant():
    assert load_releases()[0]["version"] == __version__


def test_versions_are_semver_unique_and_newest_first():
    versions = [r["version"] for r in load_releases()]
    assert all(SEMVER.match(v) for v in versions)
    assert len(set(versions)) == len(versions)
    assert versions == sorted(versions, key=_key, reverse=True)


def test_every_text_exists_in_both_languages_and_kinds_are_valid():
    for release in load_releases():
        assert release["date"]
        for lang in LANGS:
            assert release["title"].get(lang)
        assert release["items"]
        for item in release["items"]:
            assert item["kind"] in KINDS
            for lang in LANGS:
                assert item["text"].get(lang), (release["version"], item["text"])


def test_localized_falls_back_to_english():
    assert localized("xx")[0]["title"] == load_releases()[0]["title"]["en"]
    assert localized("PT-BR")[0]["title"] == load_releases()[0]["title"]["pt-br"]


def test_version_and_releases_endpoints(client):
    version = client.get("/api/version").json()
    assert version["version"] == __version__
    releases = client.get("/api/releases?lang=pt-br").json()["releases"]
    assert releases[0]["version"] == __version__
    assert releases[0]["items"][0]["text"]


def test_release_notes_script_prints_markdown_and_rejects_unknown_versions():
    script = str(ROOT / "scripts" / "release_notes.py")
    ok = subprocess.run([sys.executable, script, __version__], capture_output=True, text=True, check=False)  # noqa: S603
    assert ok.returncode == 0 and ok.stdout.startswith("### ")
    bad = subprocess.run([sys.executable, script, "9.9.9"], capture_output=True, text=True, check=False)  # noqa: S603
    assert bad.returncode == 1


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
