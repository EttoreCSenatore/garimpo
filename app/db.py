from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import structlog
from sqlmodel import Session, create_engine

from app.config import settings

connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


BASELINE_REVISION = "0001"


def init_db() -> None:
    from app import models  # noqa: F401  ensure models are registered

    _enable_wal()
    run_migrations()
    _close_stale_runs()
    from app.search.fts import ensure_search_index

    ensure_search_index(engine)


def run_migrations(target_engine=None) -> None:
    """Bring the schema to the newest Alembic revision.

    A database created before migrations existed (it has tables but no ``alembic_version``)
    is adopted: it is stamped at the baseline revision, which is exactly its schema, and then
    upgraded like any other.
    """
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    target = target_engine or engine
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with target.begin() as connection:
        cfg.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "products" in tables:
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def _enable_wal() -> None:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    except Exception as exc:  # WAL is an optimisation; keep running without it
        structlog.get_logger().warning("db.wal_unavailable", error=str(exc))


def get_session() -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _close_stale_runs() -> None:
    """Runs still marked "running" at startup were interrupted by a crash or restart."""
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE scrape_runs SET status = 'failed', "
            "error_message = 'interrupted (process restarted)', completed_at = CURRENT_TIMESTAMP "
            "WHERE status = 'running'"
        )
