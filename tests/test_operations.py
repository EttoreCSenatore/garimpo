import sqlite3
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import backup
from app.config import settings
from app.heartbeat import ping
from app.main import app


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE categories (id INTEGER PRIMARY KEY);
        CREATE TABLE product_history (id INTEGER PRIMARY KEY);
        CREATE TABLE scrape_runs (id INTEGER PRIMARY KEY);
        INSERT INTO products (name) VALUES ('a'), ('b'), ('c');
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def sqlite_env(tmp_path, monkeypatch):
    db = tmp_path / "live.db"
    _make_db(db)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db}")
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "bk"))
    monkeypatch.setattr(settings, "backup_keep", 2)
    return tmp_path


def test_backup_creates_a_verified_copy_and_records_status(sqlite_env):
    path = backup.run_backup()
    assert path.exists() and path.stat().st_mode & 0o777 == 0o600
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 3
    conn.close()
    state = backup.status()
    assert state["last_backup_at"] and state["stale"] is False and state["last_backup_bytes"] > 0


def test_backup_retention_keeps_only_the_newest(sqlite_env):
    names = []
    for _ in range(4):
        names.append(backup.run_backup().name)
        time.sleep(1.05)  # file names carry second resolution
    kept = sorted(p.name for p in (sqlite_env / "bk").glob("garimpo-*.db"))
    assert kept == names[-2:]


def test_restore_test_passes_on_good_backup_and_fails_on_corrupt_one(sqlite_env):
    backup.run_backup()
    result = backup.restore_test()
    assert result["ok"] and result["products"] == 3
    assert backup.status()["last_restore_test_ok"] is True

    newest = sorted((sqlite_env / "bk").glob("garimpo-*.db"))[-1]
    newest.write_bytes(b"this is not a database" * 100)
    with pytest.raises(Exception):  # noqa: B017  sqlite3.DatabaseError or RuntimeError
        backup.restore_test()


def test_restore_test_needs_a_backup(sqlite_env):
    with pytest.raises(RuntimeError, match="no backup"):
        backup.restore_test()


def test_status_without_backups_is_stale(sqlite_env):
    state = backup.status()
    assert state["last_backup_at"] is None and state["stale"] is True


def test_backup_refuses_non_sqlite_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@localhost/db")
    assert backup.database_path() is None
    with pytest.raises(RuntimeError):
        backup.run_backup()


def test_cli_status_and_unknown_command(sqlite_env, capsys):
    assert backup.main(["status"]) == 0
    assert "last_backup_at" in capsys.readouterr().out
    assert backup.main(["nope"]) == 2


@pytest.mark.asyncio
async def test_heartbeat_pings_ok_and_fail_urls_and_never_raises():
    with respx.mock(assert_all_called=False) as mock:
        ok = mock.get("https://hc.example/abc").mock(return_value=httpx.Response(200))
        fail = mock.get("https://hc.example/abc/fail").mock(return_value=httpx.Response(200))
        assert await ping("https://hc.example/abc") is True
        assert await ping("https://hc.example/abc", ok=False) is True
        assert ok.called and fail.called
        mock.get("https://boom.example/x").mock(side_effect=httpx.ConnectError("down"))
        assert await ping("https://boom.example/x") is False
    assert await ping("") is False
    assert await ping("file:///etc/passwd") is False


def test_health_reports_staleness_and_backup():
    with TestClient(app) as client:
        data = client.get("/api/health").json()
    assert set(data["backup"]) >= {"enabled", "stale", "last_backup_at"}
    assert isinstance(data["stale"], bool)


def test_metrics_disabled_by_default_and_protected_when_enabled(monkeypatch):
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 404
        monkeypatch.setattr(settings, "metrics_enabled", True)
        monkeypatch.setattr(settings, "metrics_token", "s3cret-token")
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200
    body = ok.text
    assert "garimpo_build_info" in body and "garimpo_products{" in body
    assert "garimpo_backup_last_success_timestamp_seconds" in body


def test_backup_is_a_single_self_contained_file(sqlite_env):
    # A live WAL-mode source must not leave -wal/-shm sidecars next to the backups.
    live = sqlite_env / "live.db"
    conn = sqlite3.connect(live)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO products (name) VALUES ('d')")
    conn.commit()
    path = backup.run_backup()
    conn.close()
    leftovers = sorted(p.name for p in (sqlite_env / "bk").iterdir())
    assert leftovers == sorted([path.name, "status.json"])
    assert sqlite3.connect(path).execute("PRAGMA journal_mode").fetchone()[0] == "delete"
