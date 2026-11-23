"""Price-drop and restock alerts for watched products.

No accounts: a watch belongs to a random ``watcher_id`` kept by the browser. Delivery goes to an
ntfy topic (the server comes from configuration, never from the shopper) or to a webhook whose
host must be on the operator's exact-host allow-list, so a shopper can never point the server
at an internal address (SSRF).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse

import httpx
import structlog
from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.events import emit
from app.models import Product, ProductStatus, Watch
from app.security import resolve_allowed_url, safe_http_url

logger = structlog.get_logger()

NTFY_TOPIC_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
CHANNELS = ("ntfy", "webhook")


def available_channels() -> list[str]:
    if not settings.alerts_enabled:
        return []
    return ["ntfy"] + (["webhook"] if settings.alerts_webhook_host_list else [])


def normalize_destination(channel: str, destination: str) -> str:
    """Validate and normalise a destination; raises ``ValueError`` with a user-facing reason."""
    destination = destination.strip()
    if channel not in available_channels():
        raise ValueError(f"channel '{channel}' is not available")
    if channel == "ntfy":
        if not NTFY_TOPIC_RE.match(destination):
            raise ValueError("an ntfy topic has 8 to 64 letters, digits, '-' or '_'")
        return destination
    url = resolve_allowed_url(destination, settings.alerts_webhook_host_list)
    if url is None:
        raise ValueError("webhook host is not allowed")
    return url


def mask_destination(channel: str, destination: str) -> str:
    """What the API shows back: never the full topic or URL path (they act as secrets)."""
    if channel == "ntfy":
        return destination[:3] + "…" if len(destination) > 3 else "…"
    return (urlparse(destination).hostname or "") + "/…"


def _brl(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def deliver(channel: str, destination: str, *, title: str, message: str, link: str | None, payload: dict) -> bool:
    """Send one notification. Never raises; returns whether it was accepted."""
    link = safe_http_url(link)
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            if channel == "ntfy":
                body = {"topic": destination, "title": title, "message": message, "tags": ["shopping_cart"]}
                if link:
                    body["click"] = link
                resp = await client.post(settings.alerts_ntfy_server.rstrip("/"), json=body)
            elif channel == "webhook":
                url = resolve_allowed_url(destination, settings.alerts_webhook_host_list)
                if url is None:
                    return False
                # "text" is Slack's field, "content" Discord's; the rest is for your own endpoint.
                resp = await client.post(
                    url, json={"text": f"{title}\n{message}", "content": f"{title}\n{message}", **payload}
                )
            else:
                return False
        return resp.status_code < 400
    except Exception as exc:
        logger.warning("alerts.delivery_failed", channel=channel, error=type(exc).__name__)
        return False


def _buyable(product: Product, size: str | None) -> bool:
    if product.status == ProductStatus.DISAPPEARED:
        return False
    if size:
        return size in (product.sizes or [])
    return bool(product.available)


async def process(product: Product) -> int:
    """Evaluate every watch of ``product`` after a scrape; returns the notifications sent."""
    if not settings.alerts_enabled:
        return 0
    with session_scope() as session:
        watches = session.exec(select(Watch).where(Watch.product_id == product.id)).all()
    sent = 0
    price = product.price
    for watch in watches:
        buyable = _buyable(product, watch.size)
        previous = watch.baseline_price
        label = f" (tamanho {watch.size})" if watch.size else ""
        base = {"product": {"id": product.id, "name": product.name, "url": product.url, "price": str(price)}}

        drop_ok = restock_ok = True
        drop = (
            price is not None
            and previous is not None
            and price < previous
            and buyable
            and (watch.target_price is None or price <= watch.target_price)
        )
        if drop:
            drop_ok = await deliver(
                watch.channel,
                watch.destination,
                title=f"Baixou de preço: {product.name}{label}",
                message=f"Agora {_brl(price)} (antes {_brl(previous)}).",
                link=product.url,
                payload={"event": "price_drop", "previous_price": str(previous), **base},
            )
            sent += int(drop_ok)
        restock = buyable and not watch.last_available
        if restock:
            restock_ok = await deliver(
                watch.channel,
                watch.destination,
                title=f"Voltou ao estoque: {product.name}{label}",
                message=f"Disponível por {_brl(price)}.",
                link=product.url,
                payload={"event": "restock", **base},
            )
            sent += int(restock_ok)

        # A failed delivery keeps the old state, so the next scrape tries again.
        with session_scope() as session:
            row = session.get(Watch, watch.id)
            if row is None:
                continue
            if drop_ok and price is not None:
                row.baseline_price = price
            if restock_ok:
                row.last_available = buyable
            if (drop and drop_ok) or (restock and restock_ok):
                row.last_notified_at = datetime.now(UTC)
            session.add(row)
            session.commit()
    if sent:
        emit({"event_type": "garimpo.alerts.sent", "product_id": product.id, "count": sent})
    return sent
