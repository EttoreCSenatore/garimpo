"""Report on the database migrations a pull request adds (Markdown), and test them.

For every migration the PR adds: the SQL it runs (offline mode, SQLite dialect), the operations
that delete data or rebuild a table, and whether a migration that already exists on the base
branch was edited or deleted (never do that: databases have already run it).
Then a back-and-forth test: upgrade to head, downgrade to base, upgrade again.

Usage: python scripts/migrations_report.py --base origin/main [--output report.md]
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VERSIONS = "app/migrations/versions"
DESTRUCTIVE = re.compile(r"\b(DROP TABLE|DROP COLUMN|DROP INDEX|DELETE FROM)\b", re.IGNORECASE)
REBUILD = re.compile(r"_alembic_tmp_", re.IGNORECASE)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def changed_files(base: str) -> dict[str, str]:
    """{path: status letter} for migration files changed between the base and HEAD."""
    out = git("diff", "--name-status", f"{base}...HEAD", "--", VERSIONS)
    return {line.split("\t")[-1]: line[0] for line in out.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", default="report.md")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/report.db"
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config()
        cfg.set_main_option("script_location", str(ROOT / "app" / "migrations"))
        script = ScriptDirectory.from_config(cfg)

        changed = changed_files(args.base)
        problems: list[str] = []
        sections: list[str] = []
        for path, status in sorted(changed.items()):
            if status in ("M", "D", "R"):
                verb = "deleted" if status == "D" else "edited or renamed"
                problems.append(
                    f"`{path}` already exists on `{args.base}` and was {verb}. Add a new migration instead."
                )

        added = {p for p, s in changed.items() if s == "A"}
        for rev in script.walk_revisions(base="base", head="heads"):
            if not any(Path(p).name == Path(rev.path).name for p in added):
                continue
            buffer = io.StringIO()
            cfg.output_buffer = buffer
            command.upgrade(cfg, f"{rev.down_revision or 'base'}:{rev.revision}", sql=True)
            sql = buffer.getvalue()
            # Alembic's own bookkeeping is noise in a review.
            sql = re.sub(r"CREATE TABLE alembic_version \(.*?\);\n", "", sql, flags=re.S)
            sql = re.sub(r"^(INSERT INTO|UPDATE|DELETE FROM) alembic_version.*;\n?", "", sql, flags=re.M)
            sql = "\n".join(line.rstrip() for line in sql.splitlines() if line.strip())
            flags = []
            if DESTRUCTIVE.search(sql):
                flags.append("**Deletes data or schema** (the automatic rollback never undoes a migration)")
            if REBUILD.search(sql):
                flags.append("Rebuilds a table (SQLite batch mode): can be slow on large tables")
            sections.append(
                f"### `{rev.revision}`: {rev.doc.splitlines()[0] if rev.doc else ''}\n\n"
                + "".join(f"- {f}\n" for f in flags)
                + f"\n<details><summary>SQL</summary>\n\n```sql\n{sql}\n```\n\n</details>\n"
            )

        # Back and forth on a throwaway database.
        roundtrip = "passed"
        try:
            from sqlalchemy import create_engine

            engine = create_engine(os.environ["DATABASE_URL"])
            with engine.begin() as conn:
                cfg.attributes["connection"] = conn
                cfg.output_buffer = None
                command.upgrade(cfg, "head")
                command.downgrade(cfg, "base")
                command.upgrade(cfg, "head")
        except Exception as exc:
            roundtrip = f"FAILED: {exc}"
            problems.append(f"Upgrade, downgrade, upgrade test failed: {exc}")

    lines = ["## Database migrations\n"]
    if not added:
        lines.append("This pull request adds no migration.\n")
    else:
        lines.append(
            f"{len(added)} new migration file(s). Back-and-forth test (upgrade, downgrade, upgrade): **{roundtrip}**.\n"
        )
    if problems:
        lines.append("### Problems\n")
        lines.extend(f"- {p}" for p in problems)
        lines.append("")
    lines.extend(sections)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
