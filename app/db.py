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
