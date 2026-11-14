from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import time
from pathlib import Path

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class SplunkHECLogger:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        batch_size: int | None = None,
        verify_ssl: bool | None = None,
        buffer_file: str | None = None,
        buffer_max_lines: int | None = None,
    ) -> None:
        self.url = url or settings.splunk_hec_url
        self.token = token if token is not None else settings.splunk_hec_token
        self.batch_size = batch_size or settings.splunk_hec_batch_size
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.splunk_hec_verify_ssl
        self.buffer_file = buffer_file or settings.splunk_buffer_file
        self.buffer_max_lines = buffer_max_lines or settings.splunk_buffer_max_lines
        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._flush_task: asyncio.Task | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                http2=True,
                verify=self.verify_ssl,
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    def _build_event(self, event: dict) -> dict:
        event_type = event.get("event_type", "garimpo.event")
        return {
            "time": event.get("_time", time.time()),
            "host": event.get("host", socket.gethostname()),
            "source": "garimpo",
            "sourcetype": "garimpo",
            "event": {
                "event_type": event_type,
                **event,
            },
        }

    async def send(self, event: dict) -> None:
        hec_event = self._build_event(event)
        async with self._lock:
            self._buffer.append(hec_event)
            if len(self._buffer) >= self.batch_size:
                await self._flush_locked()

    async def flush(self) -> None:
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self) -> None:
        """Send everything pending (buffer file first, then memory).

        Events that could not be delivered replace the contents of the buffer
        file, so nothing is duplicated and delivered events are removed.
        """
        pending = self._read_buffer_file() + self._buffer
        self._buffer = []
        if not pending:
            return

        failed: list[dict] = []
        for i in range(0, len(pending), self.batch_size):
            chunk = pending[i : i + self.batch_size]
            if not await self._send_chunk(chunk):
                # Splunk is unreachable or rejecting us: keep this and all later events
                # instead of burning retries on every remaining chunk.
                failed = pending[i:]
                break
        self._write_buffer_file(failed)

    async def _send_chunk(self, events: list[dict]) -> bool:
        if not self.token:
            logger.warning("splunk_hec.token_not_set", buffered=len(events))
            return False

        payload = "\n".join(json.dumps(e) for e in events)
        headers = {"Authorization": f"Splunk {self.token}", "Content-Type": "application/json"}

        for attempt in range(3):
            try:
                client = await self._get_client()
                resp = await client.post(self.url, content=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return True
                if resp.status_code == 400:
                    logger.error("splunk_hec.bad_request", status=resp.status_code, body=resp.text[:500])
                    return False
                if resp.status_code in (401, 403):
                    logger.error("splunk_hec.auth_error", status=resp.status_code)
                    return False
                await asyncio.sleep(2 ** attempt)
            except httpx.HTTPError as exc:
                logger.warning("splunk_hec.http_error", attempt=attempt, error=str(exc))
                await asyncio.sleep(2 ** attempt)
            except Exception as exc:
                logger.error("splunk_hec.unexpected_error", error=str(exc))
                return False
        return False

    def _read_buffer_file(self) -> list[dict]:
        path = Path(self.buffer_file)
        if not path.exists():
            return []
        events: list[dict] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("splunk_hec.buffer_bad_line")
        except OSError as exc:
            logger.error("splunk_hec.buffer_read_error", error=str(exc))
        return events

    def _write_buffer_file(self, events: list[dict]) -> None:
        """Replace the buffer file with ``events`` (capped); remove it when empty."""
        path = Path(self.buffer_file)
        if not events:
            with contextlib.suppress(FileNotFoundError, OSError):
                path.unlink()
            return
        events = events[-self.buffer_max_lines :]
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
            os.replace(tmp, path)
        except OSError as exc:
            logger.error("splunk_hec.buffer_write_error", error=str(exc))

    async def aclose(self) -> None:
        await self.flush()
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_hec_logger: SplunkHECLogger | None = None


def get_hec_logger() -> SplunkHECLogger:
    global _hec_logger
    if _hec_logger is None:
        _hec_logger = SplunkHECLogger()
    return _hec_logger
