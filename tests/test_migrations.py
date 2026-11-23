import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

from app import models  # noqa: F401
from app.db import BASELINE_REVISION, run_migrations
from app.migrations import include_object


def _head() -> str:
    from pathlib import Path

    from alembic.config import Config

    import app.db as db

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(db.__file__).parent / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _engine(tmp_path, name="m.db"):
    return create_engine(f"sqlite:///{tmp_path / name}")


def test_fresh_database_gets_the_full_schema_at_head(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == _head()
    assert {"products", "categories", "product_history", "scrape_runs"} <= set(inspect(engine).get_table_names())


def test_migrations_and_models_agree(tmp_path):
    """A model change without a migration fails here (run: alembic revision --autogenerate)."""
    engine = _engine(tmp_path)
    run_migrations(engine)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_object": include_object, "compare_type": True})
        diff = compare_metadata(ctx, SQLModel.metadata)
    assert diff == []


def test_upgrade_downgrade_upgrade_roundtrip(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    import app.db as db

    engine = _engine(tmp_path)
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(db.__file__).parent / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        assert not {"products", "scrape_runs"} & set(inspect(conn).get_table_names())
        command.upgrade(cfg, "head")
        assert "products" in set(inspect(conn).get_table_names())


def test_legacy_database_is_adopted_without_losing_data(tmp_path):
    """A database made by the pre-Alembic create_all() is stamped, upgraded and keeps its rows."""
    engine = _engine(tmp_path, "legacy.db")
    # The 0.4.0 schema: exactly what the baseline revision describes.
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    import app.db as db

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(db.__file__).parent / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, BASELINE_REVISION)
        conn.execute(text("DROP TABLE alembic_version"))  # as if it never had Alembic
        conn.execute(
            text(
                "INSERT INTO products (id, slug, url, name, currency, available, status, scraped_at, "
                "created_at, updated_at, view_count) VALUES (1, 's', 'u', 'Legacy', 'BRL', 1, 'ACTIVE', "
                "'2026-01-01', '2026-01-01', '2026-01-01', 0)"
            )
        )
    run_migrations(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == _head()
        assert conn.execute(text("SELECT name FROM products WHERE id = 1")).scalar() == "Legacy"


def test_running_twice_is_a_noop(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)
    conn = sqlite3.connect(tmp_path / "m.db")
    assert conn.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0] == 1


@pytest.fixture(autouse=True)
def _quiet():
    yield
