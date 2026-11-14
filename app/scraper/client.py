from __future__ import annotations

import asyncio
import random
import time
from typing import Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class RateLimitedClient:
    def __init__(
        self,
        user_agent: Optional[str] = None,
        base_url: Optional[str] = None,
        requests_per_second: Optional[float] = None,
        jitter_min_ms: Optional[int] = None,
        jitter_max_ms: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.user_agent = user_agent or settings.user_agent
        self.base_url = base_url or settings.base_url
        self.requests_per_second = requests_per_second or settings.requests_per_second
        self.jitter_min_ms = jitter_min_ms if jitter_min_ms is not None else settings.jitter_min_ms
        self.jitter_max_ms = jitter_max_ms if jitter_max_ms is not None else settings.jitter_max_ms
        self.max_retries = max_retries if max_retries is not None else settings.max_retries

        self._min_interval = 1.0 / max(self.requests_per_second, 0.01)
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

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
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            jitter = random.uniform(self.jitter_min_ms / 1000.0, self.jitter_max_ms / 1000.0)
            await asyncio.sleep(jitter)
            self._last_request_time = time.monotonic()

    async def get(self, path: str, *, retries: Optional[int] = None) -> httpx.Response:
        retries = retries if retries is not None else self.max_retries
        attempt = 0
        while True:
            await self._throttle()
            client = await self.get_client()
            try:
                resp = await client.get(path)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < retries:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            "scraper.retry",
                            url=path,
                            status=resp.status_code,
                            attempt=attempt,
                            wait=wait,
                        )
                        await asyncio.sleep(wait)
                        attempt += 1
                        continue
                return resp
            except httpx.HTTPError as exc:
                if attempt < retries:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "scraper.retry",
                        url=path,
                        error=str(exc),
                        attempt=attempt,
                        wait=wait,
                    )
                    await asyncio.sleep(wait)
                    attempt += 1
                    continue
                raise

    async def get_raw(self, url: str, *, retries: Optional[int] = None) -> httpx.Response:
        retries = retries if retries is not None else self.max_retries
        attempt = 0
        while True:
            await self._throttle()
            client = await self.get_client()
            try:
                resp = await client.get(url)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < retries:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            "scraper.retry",
                            url=url,
                            status=resp.status_code,
                            attempt=attempt,
                            wait=wait,
                        )
                        await asyncio.sleep(wait)
                        attempt += 1
                        continue
                return resp
            except httpx.HTTPError as exc:
                if attempt < retries:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "scraper.retry",
                        url=url,
                        error=str(exc),
                        attempt=attempt,
                        wait=wait,
                    )
                    await asyncio.sleep(wait)
                    attempt += 1
                    continue
                raise

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
