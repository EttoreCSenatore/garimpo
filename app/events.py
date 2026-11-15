"""Structured domain events (scrape runs, product changes, errors).

Events go through structlog, so they land on stdout as JSON in production and can be
shipped by whatever collects container logs (Loki, CloudWatch, a plain ``docker logs``).
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("garimpo.events")


def emit(event: dict) -> None:
    """Log one event; ``event_type`` becomes the log message, the rest are fields."""
    fields = dict(event)
    event_type = str(fields.pop("event_type", "garimpo.event"))
    if event_type.startswith("garimpo.error"):
        logger.error(event_type, **fields)
    else:
        logger.info(event_type, **fields)
