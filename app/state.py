"""Process-wide runtime state shared by the API and background tasks.

Kept separate from ``app.api.routes`` so that ``app.tasks`` does not have to
import the router (which previously created a circular dependency).
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

active_workers: dict[str, int] = {"full": 0, "incremental": 0, "single": 0}

# Product ids with a single-product refresh already queued or running.
inflight_single: set[int] = set()
MAX_INFLIGHT_SINGLE = 25

# Locks that stop two runs of the same kind from overlapping.
run_locks: dict[str, asyncio.Lock] = {}

# Strong references to fire-and-forget tasks (the event loop only keeps weak ones).
_background_tasks: set[asyncio.Task] = set()


def get_run_lock(name: str) -> asyncio.Lock:
    lock = run_locks.get(name)
    if lock is None:
        lock = run_locks[name] = asyncio.Lock()
    return lock


def spawn(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
