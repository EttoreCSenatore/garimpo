from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.splunk_hec import SplunkHECLogger


@pytest.fixture
def hec_logger(tmp_path):
    buffer_file = tmp_path / "events.jsonl"
    logger = SplunkHECLogger(
        url="https://localhost:8088/services/collector/event",
        token="test-token",
        batch_size=3,
        verify_ssl=False,
        buffer_file=str(buffer_file),
        buffer_max_lines=100,
    )
    yield logger


@pytest.mark.asyncio
async def test_splunk_hec_batch(hec_logger):
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://localhost:8088/services/collector/event").mock(
            return_value=httpx.Response(200, json={"text": "Success", "code": 0})
        )

        for i in range(5):
            await hec_logger.send({"event_type": "garimpo.product.scraped", "id": i, "name": f"Product {i}"})

        await hec_logger.flush()

        calls = mock.calls
        assert len(calls) >= 2

        for call in calls:
            body = call.request.content.decode()
            events = [json.loads(line) for line in body.strip().split("\n") if line.strip()]
            assert len(events) <= 3
            for event in events:
                assert event["sourcetype"] == "garimpo"
                assert event["source"] == "garimpo"
                assert "event_type" in event["event"]


@pytest.mark.asyncio
async def test_splunk_hec_buffer_on_failure(hec_logger, tmp_path):
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://localhost:8088/services/collector/event").mock(
            return_value=httpx.Response(500)
        )

        await hec_logger.send({"event_type": "garimpo.product.scraped", "id": 1, "name": "Test"})
        await hec_logger.flush()

    buffer_path = Path(hec_logger.buffer_file)
    assert buffer_path.exists()
    lines = buffer_path.read_text().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event["event"]["event_type"] == "garimpo.product.scraped"


@pytest.mark.asyncio
async def test_splunk_hec_no_token(hec_logger, tmp_path):
    hec_logger.token = ""
    with respx.mock(assert_all_called=False):
        await hec_logger.send({"event_type": "garimpo.product.scraped", "id": 1})
        await hec_logger.flush()

    buffer_path = Path(hec_logger.buffer_file)
    assert buffer_path.exists()


@pytest.mark.asyncio
async def test_splunk_hec_retry_on_5xx(hec_logger):
    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"text": "Success"})

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://localhost:8088/services/collector/event").mock(side_effect=handler)

        hec_logger.batch_size = 1
        await hec_logger.send({"event_type": "test", "id": 1})
        await hec_logger.flush()

    assert call_count >= 3


@pytest.mark.asyncio
async def test_splunk_event_structure(hec_logger):
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://localhost:8088/services/collector/event").mock(
            return_value=httpx.Response(200, json={"text": "Success"})
        )

        await hec_logger.send({"event_type": "garimpo.product.scraped", "id": 42, "name": "Test Product"})
        await hec_logger.flush()

        call = mock.calls[0]
        body = call.request.content.decode()
        event = json.loads(body.strip().split("\n")[0])

        assert "time" in event
        assert "host" in event
        assert event["source"] == "garimpo"
        assert event["sourcetype"] == "garimpo"
        assert event["event"]["event_type"] == "garimpo.product.scraped"
        assert event["event"]["id"] == 42
