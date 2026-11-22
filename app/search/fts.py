"""Full-text product search with SQLite FTS5.

The ``products_fts`` virtual table indexes the text fields of ``products``
(external content, kept in sync by triggers). It folds accents and case
(``tenis`` matches ``Tênis``), matches words in any order and by prefix
(``bola`` matches ``bolas``), and ranks results with BM25, weighting a match in
the product name above brand, breadcrumbs and slug. Descriptions are deliberately
not indexed: they mention other products ("combine com sua camiseta") and made
irrelevant items match.

On databases without FTS5 (for example PostgreSQL via ``DATABASE_URL``) the
callers fall back to ``LIKE`` matching, so this module is an optimisation, not
a requirement.
"""

from __future__ import annotations

import re

import structlog
from sqlalchemy import Engine, Float, Integer, bindparam, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

logger = structlog.get_logger()

FTS_TABLE = "products_fts"
# Indexed columns: name, brand, breadcrumbs, slug.
# BM25 weights follow the same order: a hit in the name matters most.

# Plain SQL literals (no string building): user text only ever reaches SQLite as a
# bound parameter of MATCH.
_CREATE_TABLE = (
    "CREATE VIRTUAL TABLE products_fts USING fts5("
    "name, brand, breadcrumbs, slug, "
    "content='products', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
)
_TRIGGERS = (
    "CREATE TRIGGER IF NOT EXISTS products_fts_ai AFTER INSERT ON products BEGIN "
    "INSERT INTO products_fts(rowid, name, brand, breadcrumbs, slug) "
    "VALUES (new.id, new.name, new.brand, new.breadcrumbs, new.slug); END",
    "CREATE TRIGGER IF NOT EXISTS products_fts_ad AFTER DELETE ON products BEGIN "
    "INSERT INTO products_fts(products_fts, rowid, name, brand, breadcrumbs, slug) "
    "VALUES ('delete', old.id, old.name, old.brand, old.breadcrumbs, old.slug); END",
    # Only text changes touch the index (view_count updates on every product view do not).
    "CREATE TRIGGER IF NOT EXISTS products_fts_au "
    "AFTER UPDATE OF name, brand, breadcrumbs, slug ON products BEGIN "
    "INSERT INTO products_fts(products_fts, rowid, name, brand, breadcrumbs, slug) "
    "VALUES ('delete', old.id, old.name, old.brand, old.breadcrumbs, old.slug); "
    "INSERT INTO products_fts(rowid, name, brand, breadcrumbs, slug) "
    "VALUES (new.id, new.name, new.brand, new.breadcrumbs, new.slug); END",
)
INDEXED_COLUMNS = ["name", "brand", "breadcrumbs", "slug"]
_DROP_OLD = (
    "DROP TRIGGER IF EXISTS products_fts_ai",
    "DROP TRIGGER IF EXISTS products_fts_ad",
    "DROP TRIGGER IF EXISTS products_fts_au",
    "DROP TABLE IF EXISTS products_fts",
)
_REBUILD = "INSERT INTO products_fts(products_fts) VALUES ('rebuild')"
_RANKED = (
    "SELECT rowid AS id, bm25(products_fts, 10.0, 5.0, 3.0, 2.0) AS rank "
    "FROM products_fts WHERE products_fts MATCH :match"
)

# Words only: anything else (quotes, operators, parentheses) never reaches MATCH.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
MAX_TOKENS = 8

# Cached on the Engine object itself: id(engine) can be reused after garbage collection.
_FLAG = "_garimpo_fts_available"


def ensure_search_index(engine: Engine) -> bool:
    """Create the FTS table and triggers if missing; return whether FTS is usable."""
    if engine.dialect.name != "sqlite":
        setattr(engine, _FLAG, False)
        return False
    try:
        with engine.begin() as conn:
            exists = conn.exec_driver_sql(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (FTS_TABLE,)
            ).first()
            if exists:
                columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(products_fts)")]
                if columns != INDEXED_COLUMNS:
                    # Index created by an older version with other columns: recreate it.
                    for statement in _DROP_OLD:
                        conn.exec_driver_sql(statement)
                    exists = None
            if not exists:
                conn.exec_driver_sql(_CREATE_TABLE)
            for statement in _TRIGGERS:
                conn.exec_driver_sql(statement)
            if not exists:
                # Index the rows that were there before the table existed.
                conn.exec_driver_sql(_REBUILD)
    except OperationalError as exc:  # SQLite built without FTS5
        logger.warning("search.fts_unavailable", error=str(exc))
        setattr(engine, _FLAG, False)
        return False
    setattr(engine, _FLAG, True)
    return True


def fts_available(session: Session) -> bool:
    engine = session.get_bind()
    flag = getattr(engine, _FLAG, None)
    return ensure_search_index(engine) if flag is None else flag


def _phrase(term: str) -> str | None:
    """One user term as a quoted FTS phrase with a prefix match on its last word."""
    words = _TOKEN_RE.findall(term.lower())[:MAX_TOKENS]
    return f'"{" ".join(words)}"*' if words else None


def match_all(text_query: str) -> str | None:
    """Every word must match (any order, any column): ``"nike"* AND "air"*``."""
    words = _TOKEN_RE.findall(text_query.lower())[:MAX_TOKENS]
    return " AND ".join(f'"{w}"*' for w in words) or None


def match_any(terms: list[str]) -> str | None:
    """At least one of the terms must match: ``("chuteira"* OR "futebol"*)``."""
    phrases = [p for p in (_phrase(t) for t in terms) if p]
    return "(" + " OR ".join(phrases) + ")" if phrases else None


def combine_and(*groups: str | None) -> str | None:
    parts = [g for g in groups if g]
    return " AND ".join(parts) or None


def ranked_matches(match: str, name: str = "fts"):
    """Subquery of ``(id, rank)`` for products matching ``match``; lower rank is better.

    ``name`` labels the subquery; the bind parameter is unique per call, so several
    of these can be joined in one statement.
    """
    return (
        text(_RANKED)
        .bindparams(bindparam("match", value=match, unique=True))
        .columns(id=Integer, rank=Float)
        .subquery(name)
    )
