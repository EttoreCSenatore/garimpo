from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import structlog
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    from app import models  # noqa: F401  ensure models are registered

    SQLModel.metadata.create_all(engine)
    _enable_wal()
    _ensure_indexes()
    _close_stale_runs()
    from app.search.fts import ensure_search_index

    ensure_search_index(engine)


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


# create_all() does not add indexes to tables that already exist, so they are created idempotently.
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_products_category_id ON products (category_id)",
    "CREATE INDEX IF NOT EXISTS ix_products_brand ON products (brand)",
    "CREATE INDEX IF NOT EXISTS ix_products_status ON products (status)",
    "CREATE INDEX IF NOT EXISTS ix_products_view_count ON products (view_count)",
    "CREATE INDEX IF NOT EXISTS ix_product_history_scraped_at ON product_history (product_id, scraped_at)",
    "CREATE INDEX IF NOT EXISTS ix_scrape_runs_started_at ON scrape_runs (started_at)",
)


def _ensure_indexes() -> None:
    with engine.begin() as conn:
        for statement in _INDEXES:
            conn.exec_driver_sql(statement)


def _close_stale_runs() -> None:
    """Runs still marked "running" at startup were interrupted by a crash or restart."""
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE scrape_runs SET status = 'failed', "
            "error_message = 'interrupted (process restarted)', completed_at = CURRENT_TIMESTAMP "
            "WHERE status = 'running'"
        )
