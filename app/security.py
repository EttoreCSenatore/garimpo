"""Security helpers: token checks, URL validation, rate limiting, headers."""
from __future__ import annotations

import ipaddress
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


def tokens_match(supplied: str | None, expected: str) -> bool:
    """Constant-time token comparison; an empty expected token never matches."""
    if not supplied or not expected:
        return False
    return secrets.compare_digest(supplied.encode(), expected.encode())


def host_allowed(host: str, allowed: list[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == a or host.endswith("." + a) for a in allowed)


def safe_http_url(url: str | None, allowed_hosts: list[str] | None = None) -> str | None:
    """Return ``url`` only if it is an absolute http(s) URL (optionally host-restricted)."""
    if not url or len(url) > 2048:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    try:
        ipaddress.ip_address(parsed.hostname)
        return None  # never allow literal IPs
    except ValueError:
        pass
    if allowed_hosts is not None and not host_allowed(parsed.hostname, allowed_hosts):
        return None
    return url.strip()


class RateLimiter:
    """In-process sliding-window limiter keyed by client address."""

    def __init__(self, name: str, limit_getter, window: float = 60.0, max_keys: int = 10_000) -> None:
        self.name = name
        self.limit_getter = limit_getter
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request) -> None:
        limit = self.limit_getter()
        if limit <= 0:
            return
        now = time.monotonic()
        key = self._client_key(request)
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= limit:
            retry = max(1, int(self.window - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)
        if len(self._hits) > self.max_keys:
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                del self._hits[k]


chat_rate_limit = RateLimiter("chat", lambda: settings.chat_rate_limit_per_minute)
image_rate_limit = RateLimiter("image", lambda: settings.image_rate_limit_per_minute)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        # The API serves JSON and proxied images only; nothing should render as a page.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response
