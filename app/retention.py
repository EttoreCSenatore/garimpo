"""Housekeeping: prune old scrape runs (and, if configured, old price history)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.config import settings
from app.db import session_scope
from app.events import emit
from app.models import ProductHistory, ScrapeRun


def apply_retention() -> dict[str, int]:
    """Delete finished runs older than RETENTION_RUNS_DAYS and history older than RETENTION_HISTORY_DAYS."""
    now = datetime.now(UTC)
    removed = {"scrape_runs": 0, "product_history": 0}
    with session_scope() as session:
        if settings.retention_runs_days > 0:
            cutoff = now - timedelta(days=settings.retention_runs_days)
            result = session.exec(
                delete(ScrapeRun).where(ScrapeRun.completed_at.is_not(None), ScrapeRun.completed_at < cutoff)
            )
            removed["scrape_runs"] = result.rowcount or 0
        if settings.retention_history_days > 0:
            cutoff = now - timedelta(days=settings.retention_history_days)
            result = session.exec(delete(ProductHistory).where(ProductHistory.scraped_at < cutoff))
            removed["product_history"] = result.rowcount or 0
        session.commit()
    return removed


async def retention_job() -> None:
    import asyncio

    removed = await asyncio.to_thread(apply_retention)
    emit({"event_type": "garimpo.retention.applied", **removed})
