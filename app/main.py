from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone

import structlog
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import init_db
from app.splunk_hec import get_hec_logger

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()

scheduler: AsyncIOScheduler | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    init_db()
    logger.info("app.startup", env=settings.app_env)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_full_refresh_job,
        "interval",
        minutes=settings.full_refresh_interval_minutes,
        id="full_refresh",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    scheduler.add_job(
        run_incremental_refresh_job,
        "interval",
        minutes=settings.incremental_refresh_interval_minutes,
        id="incremental_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler.started")

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    hec = get_hec_logger()
    await hec.aclose()
    logger.info("app.shutdown")


async def run_full_refresh_job() -> None:
    from app.tasks import run_full_refresh_async
    asyncio.create_task(run_full_refresh_async())


async def run_incremental_refresh_job() -> None:
    from app.tasks import run_incremental_refresh_async
    asyncio.create_task(run_incremental_refresh_async())


app = FastAPI(
    title="Tivolli Scraper API",
    description="Scraper de produtos e API REST para tivolli.com.br com integração Splunk HEC",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
