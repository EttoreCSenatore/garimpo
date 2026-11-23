"""Alembic migrations (see env.py and versions/)."""

# FTS5 virtual tables and their shadow tables are managed by app/search/fts.py, not by migrations.
FTS_PREFIX = "products_fts"


def include_object(obj, name, type_, reflected, compare_to):
    """Keep the full-text index out of autogenerate and schema comparisons."""
    return not (type_ == "table" and name and name.startswith(FTS_PREFIX))
