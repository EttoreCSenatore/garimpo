"""Test environment: isolated DB, no background scraping, no network.

These variables must be set before ``app.config`` is first imported.
"""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="garimpo-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_TOKEN"] = ""


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    from app import security

    security.chat_rate_limit._hits.clear()
    security.image_rate_limit._hits.clear()
    yield
    security.chat_rate_limit._hits.clear()
    security.image_rate_limit._hits.clear()
