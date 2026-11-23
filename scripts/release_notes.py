"""Print the GitHub Release notes (Markdown, English) for a version from app/releases.yaml.

Usage: python scripts/release_notes.py 0.3.0 [--title]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.releases import load_releases  # noqa: E402

HEADINGS = {"new": "New", "improvement": "Improvements", "fix": "Fixes", "security": "Security"}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: release_notes.py VERSION [--title]", file=sys.stderr)
        return 2
    version = argv[0].removeprefix("v")
    release = next((r for r in load_releases() if r["version"] == version), None)
    if release is None:
        print(f"version {version} not found in app/releases.yaml", file=sys.stderr)
        return 1
    if "--title" in argv:
        print(f"{release['version']}: {release['title']['en']}")
        return 0
    lines: list[str] = []
    for kind, heading in HEADINGS.items():
        items = [i for i in release["items"] if i["kind"] == kind]
        if items:
            lines.append(f"### {heading}\n")
            lines.extend(f"- {i['text']['en']}" for i in items)
            lines.append("")
    print("\n".join(lines).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
