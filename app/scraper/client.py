from __future__ import annotations

import asyncio
import random
import time
from urllib.parse import parse_qs, urlparse

import httpx
import structlog

from app.config import settings
from app.security import host_allowed

logger = structlog.get_logger()


_last_request = [0.0]
_throttle_locks: dict[int, asyncio.Lock] = {}


def _throttle_lock() -> asyncio.Lock:
    """One lock per running event loop (locks cannot be shared across loops)."""
    loop_id = id(asyncio.get_running_loop())
    lock = _throttle_locks.get(loop_id)
    if lock is None:
        _throttle_locks.clear()
        lock = _throttle_locks[loop_id] = asyncio.Lock()
    return lock


class DisallowedRequestError(ValueError):
    """Raised when a request would leave the target site or hit a robots-disallowed path."""


class RateLimitedClient:
    def __init__(
        self,
        user_agent: str | None = None,
        base_url: str | None = None,
        requests_per_second: float | None = None,
        jitter_min_ms: int | None = None,
        jitter_max_ms: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.user_agent = user_agent or settings.user_agent
        self.base_url = base_url or settings.base_url
        self.requests_per_second = requests_per_second or settings.requests_per_second
        self.jitter_min_ms = jitter_min_ms if jitter_min_ms is not None else settings.jitter_min_ms
        self.jitter_max_ms = jitter_max_ms if jitter_max_ms is not None else settings.jitter_max_ms
        self.max_retries = max_retries if max_retries is not None else settings.max_retries

        self._min_interval = 1.0 / max(self.requests_per_second, 0.01)
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                http2=True,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def _throttle(self) -> None:
        # The limiter is process-wide: parallel jobs (full + single refreshes) share one
        # budget, so the target site never sees more than ``requests_per_second``.
        async with _throttle_lock():
            now = time.monotonic()
            elapsed = now - _last_request[0]
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            jitter = random.uniform(self.jitter_min_ms / 1000.0, self.jitter_max_ms / 1000.0)
            await asyncio.sleep(jitter)
            _last_request[0] = time.monotonic()

    def _check_allowed(self, target: str) -> None:
        """Only crawl the configured site, and never robots.txt-disallowed paths."""
        parsed = urlparse(target)
        if parsed.scheme or parsed.netloc:
            base_host = urlparse(self.base_url).hostname or ""
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise DisallowedRequestError(f"unsupported URL: {target}")
            if not host_allowed(parsed.hostname, [base_host.lower().removeprefix("www.")]):
                raise DisallowedRequestError(f"host not allowed: {parsed.hostname}")
        path = parsed.path or "/"
        if any(path == d or path.startswith(d.rstrip("/") + "/") for d in settings.robots_disallowed):
            raise DisallowedRequestError(f"path disallowed by robots.txt: {path}")
        blocked = {k.lower() for k in parse_qs(parsed.query, keep_blank_values=True)} & settings.robots_disallowed_params
        if blocked:
            raise DisallowedRequestError(f"query parameter disallowed by robots.txt: {sorted(blocked)[0]}")

    async def get(self, path: str, *, retries: int | None = None) -> httpx.Response:
        """GET a path (or absolute URL) on the target site with throttling and retries."""
        self._check_allowed(path)
        retries = retries if retries is not None else self.max_retries
        attempt = 0
        while True:
            await self._throttle()
            client = await self.get_client()
            try:
                resp = await client.get(path)
                retryable = resp.status_code == 429 or resp.status_code >= 500
                if not (retryable and attempt < retries):
                    return resp
                reason = {"status": resp.status_code}
            except httpx.HTTPError as exc:
                if attempt >= retries:
                    raise
                reason = {"error": str(exc)}
            wait = (2**attempt) + random.uniform(0, 1)
            logger.warning("scraper.retry", url=path, attempt=attempt, wait=wait, **reason)
            await asyncio.sleep(wait)
            attempt += 1

    async def get_raw(self, url: str, *, retries: int | None = None) -> httpx.Response:
        """Alias of :meth:`get` kept for call sites that pass absolute URLs."""
        return await self.get(url, retries=retries)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
