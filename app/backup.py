"""SQLite backups and restore tests.

``run_backup`` takes an online copy with SQLite's backup API (safe while the app writes),
verifies it, applies retention and records the result in ``status.json`` next to the copies.
``restore_test`` proves the newest backup is usable by opening a throwaway copy of it.
Run by the scheduler, or by hand: ``python -m app.backup [backup|test-restore|status]``.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.config import settings
from app.events import emit
from app.heartbeat import ping

logger = structlog.get_logger()

REQUIRED_TABLES = {"products", "categories", "product_history", "scrape_runs"}
PREFIX = "garimpo-"
STATUS_NAME = "status.json"


def database_path() -> Path | None:
    """The SQLite file of DATABASE_URL, or None for other databases (not supported here)."""
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def backup_dir() -> Path:
    if settings.backup_dir:
        return Path(settings.backup_dir)
    db = database_path()
    return (db.parent if db else Path(".")) / "backups"


def _now() -> datetime:
    return datetime.now(UTC)


def _list_backups(folder: Path) -> list[Path]:
    return sorted(folder.glob(f"{PREFIX}*.db"))


def _read_status(folder: Path) -> dict:
    try:
        return json.loads((folder / STATUS_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(folder: Path, **changes) -> None:
    status = _read_status(folder) | changes
    tmp = folder / (STATUS_NAME + ".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(tmp, folder / STATUS_NAME)


def _integrity_ok(path: Path) -> tuple[bool, int]:
    """Open a SQLite file read-only and check it: integrity, required tables, product count."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            return False, 0
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES <= tables:
            return False, 0
        return True, conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()


def run_backup() -> Path:
    """Online backup of the live database. Raises on failure (nothing is half-written)."""
    db = database_path()
    if db is None or not db.exists():
        raise RuntimeError("backups need a SQLite database file")
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)

    final = folder / f"{PREFIX}{_now():%Y%m%d-%H%M%S}.db"
    tmp = final.with_suffix(".db.tmp")
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            # The copy inherits WAL mode from the live database; a rollback-journal file is
            # self-contained (no -wal/-shm sidecars to lose or leave behind).
            dst.execute("PRAGMA journal_mode=DELETE")
        finally:
            dst.close()
    finally:
        src.close()
    try:
        ok, products = _integrity_ok(tmp)
        if not ok:
            raise RuntimeError("backup failed its integrity check")
        tmp.chmod(0o600)
        os.replace(tmp, final)
    finally:
        for leftover in (tmp, Path(f"{tmp}-wal"), Path(f"{tmp}-shm")):
            leftover.unlink(missing_ok=True)

    for old in _list_backups(folder)[: -max(settings.backup_keep, 1)]:
        old.unlink(missing_ok=True)
    _write_status(
        folder,
        last_backup_at=_now().isoformat(),
        last_backup_file=final.name,
        last_backup_bytes=final.stat().st_size,
        last_backup_products=products,
    )
    return final


def restore_test() -> dict:
    """Restore the newest backup into a throwaway copy and check it. Returns a result dict."""
    folder = backup_dir()
    backups = _list_backups(folder)
    if not backups:
        raise RuntimeError("no backup to test")
    newest = backups[-1]
    with tempfile.TemporaryDirectory(prefix="garimpo-restore-") as tmpdir:
        copy = Path(tmpdir) / "restored.db"
        shutil.copyfile(newest, copy)
        ok, products = _integrity_ok(copy)
    result = {"file": newest.name, "ok": ok, "products": products}
    _write_status(
        folder,
        last_restore_test_at=_now().isoformat(),
        last_restore_test_ok=ok,
        last_restore_test_file=newest.name,
    )
    if not ok:
        raise RuntimeError(f"restore test failed for {newest.name}")
    return result


def status() -> dict:
    """Backup health for /api/health and metrics (never raises)."""
    folder = backup_dir()
    data = _read_status(folder)
    last = data.get("last_backup_at")
    age = None
    if last:
        age = int((_now() - datetime.fromisoformat(last)).total_seconds())
    return {
        "enabled": settings.backup_enabled and database_path() is not None,
        "last_backup_at": last,
        "age_seconds": age,
        "stale": age is None or age > settings.backup_stale_hours * 3600,
        "last_backup_bytes": data.get("last_backup_bytes"),
        "last_restore_test_at": data.get("last_restore_test_at"),
        "last_restore_test_ok": data.get("last_restore_test_ok"),
    }


async def backup_job() -> None:
    """Scheduled daily backup: runs in a thread, emits events and pings the heartbeat."""
    try:
        path = await asyncio.to_thread(run_backup)
    except Exception as exc:
        logger.error("backup.failed", error=str(exc))
        emit({"event_type": "garimpo.error.backup", "error": str(exc)})
        await ping(settings.heartbeat_backup_url, ok=False)
        return
    emit({"event_type": "garimpo.backup.completed", "file": path.name, "bytes": path.stat().st_size})
    await ping(settings.heartbeat_backup_url)


async def restore_test_job() -> None:
    """Scheduled weekly restore test of the newest backup."""
    try:
        result = await asyncio.to_thread(restore_test)
    except Exception as exc:
        logger.error("backup.restore_test_failed", error=str(exc))
        emit({"event_type": "garimpo.error.restore_test", "error": str(exc)})
        await ping(settings.heartbeat_restore_url, ok=False)
        return
    emit({"event_type": "garimpo.backup.restore_tested", **result})
    await ping(settings.heartbeat_restore_url)


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "backup"
    try:
        if command == "backup":
            print(run_backup())
        elif command == "test-restore":
            print(json.dumps(restore_test()))
        elif command == "status":
            print(json.dumps(status(), indent=2))
        else:
            print("usage: python -m app.backup [backup|test-restore|status]", file=sys.stderr)
            return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
