"""Samples of pages that failed to parse, kept for debugging a store redesign."""

from __future__ import annotations

import structlog
from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.models import ParseFailure

logger = structlog.get_logger()


def record_parse_failure(url: str, error: str, *, http_status: int | None = None, html: str | None = None) -> None:
    """Store a failure with the start of the HTML; only the newest ``parse_failure_samples_keep`` stay."""
    try:
        with session_scope() as session:
            session.add(
                ParseFailure(
                    url=url[:1024],
                    error=error[:1024],
                    http_status=http_status,
                    html_sample=html[: settings.parse_sample_bytes] if html else None,
                )
            )
            session.commit()
            keep = max(settings.parse_failure_samples_keep, 1)
            stale = session.exec(select(ParseFailure.id).order_by(ParseFailure.id.desc()).offset(keep)).all()
            for failure_id in stale:
                session.delete(session.get(ParseFailure, failure_id))
            session.commit()
    except Exception as exc:  # debugging aid: never let it break a scrape
        logger.warning("failures.record_failed", error=type(exc).__name__)
