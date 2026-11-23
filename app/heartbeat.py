"""Optional heartbeat pings (Healthchecks.io style).

A monitor expects a ping every period and alerts when one is missing, so it also catches the
whole process being down. ``ok=False`` appends ``/fail`` to report an explicit failure.
Pings never raise: monitoring must not break the job it watches.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()


def _valid(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


async def ping(url: str, *, ok: bool = True) -> bool:
    """GET the heartbeat URL (empty means disabled). Returns True when the ping was delivered."""
    if not url:
        return False
    if not _valid(url):
        logger.warning("heartbeat.invalid_url")
        return False
    target = url if ok else url.rstrip("/") + "/fail"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(target, headers={"User-Agent": "garimpo-heartbeat"})
        return resp.status_code < 400
    except Exception as exc:
        logger.warning("heartbeat.failed", error=type(exc).__name__)
        return False
