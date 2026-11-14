from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

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
    except Exception:
        pass


def get_session() -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session
