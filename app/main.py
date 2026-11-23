from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

import structlog
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import init_db
from app.security import SecurityHeadersMiddleware
from app.state import spawn
from app.version import __version__

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
    settings.validate_for_runtime()
    init_db()
    logger.info("app.startup", env=settings.app_env)

    if not settings.scheduler_enabled:
        logger.info("scheduler.disabled")
        yield
        return

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_full_refresh_job,
        "interval",
        minutes=settings.full_refresh_interval_minutes,
        id="full_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC) + timedelta(minutes=1),
    )
    scheduler.add_job(
        run_incremental_refresh_job,
        "interval",
        minutes=settings.incremental_refresh_interval_minutes,
        id="incremental_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    from app.backup import backup_job, database_path, restore_test_job

    if settings.backup_enabled and database_path() is not None:
        scheduler.add_job(
            backup_job,
            "cron",
            hour=settings.backup_hour_utc,
            minute=0,
            timezone="UTC",
            id="backup",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            restore_test_job,
            "cron",
            day_of_week=settings.restore_test_weekday,
            hour=settings.backup_hour_utc + 1,
            minute=0,
            timezone="UTC",
            id="restore_test",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    logger.info("scheduler.started")

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    logger.info("app.shutdown")


async def run_full_refresh_job() -> None:
    from app.tasks import run_full_refresh_async

    spawn(run_full_refresh_async())


async def run_incremental_refresh_job() -> None:
    from app.tasks import run_incremental_refresh_async

    spawn(run_incremental_refresh_async())


app = FastAPI(
    title="Garimpo API",
    description="Scraper de produtos e API REST para tivolli.com.br",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
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
