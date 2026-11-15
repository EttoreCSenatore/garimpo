import pytest

from app import canary


@pytest.mark.asyncio
async def test_canary_reports_too_few_categories(monkeypatch):
    async def few(_client):
        return []

    monkeypatch.setattr(canary, "fetch_categories", few)
    problems = await canary.run()
    assert problems and "categories" in problems[0]
