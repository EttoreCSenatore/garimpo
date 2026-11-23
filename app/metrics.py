"""Prometheus text-format metrics, computed from the database and the backup status on request."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, func, select

from app import backup
from app.models import ParseFailure, Product, ProductStatus, ScrapeRun
from app.version import __version__


def _ts(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).timestamp()


def render(db: Session) -> str:
    lines: list[str] = []

    def metric(name: str, help_text: str, kind: str, samples: list[tuple[dict[str, str], float]]) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")
        for labels, value in samples:
            label_text = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_text}}} {value}" if label_text else f"{name} {value}")

    metric("garimpo_build_info", "Installed version.", "gauge", [({"version": __version__}, 1)])

    counts = dict(db.exec(select(Product.status, func.count()).group_by(Product.status)).all())
    metric(
        "garimpo_products",
        "Products by status.",
        "gauge",
        [({"status": s.value}, float(counts.get(s, 0))) for s in ProductStatus],
    )

    missing = db.exec(select(func.count()).select_from(Product).where(Product.missing_crawls > 0)).one()
    metric(
        "garimpo_products_missing_crawls",
        "Active products absent from the last full crawl (disappearance candidates).",
        "gauge",
        [({}, float(missing))],
    )
    stored = db.exec(select(func.count()).select_from(ParseFailure)).one()
    metric(
        "garimpo_parse_failure_samples",
        "Stored samples of pages that failed to parse (see /admin/parse-failures).",
        "gauge",
        [({}, float(stored))],
    )

    runs = db.exec(select(ScrapeRun).where(ScrapeRun.completed_at.is_not(None))).all()
    last_ok: dict[str, ScrapeRun] = {}
    last_any: dict[str, ScrapeRun] = {}
    for r in sorted(runs, key=lambda r: _ts(r.completed_at)):
        last_any[r.run_type] = r
        if r.status == "completed":
            last_ok[r.run_type] = r
    metric(
        "garimpo_last_success_timestamp_seconds",
        "Completion time of the last successful run, by type.",
        "gauge",
        [({"run_type": t}, _ts(r.completed_at)) for t, r in last_ok.items()],
    )
    metric(
        "garimpo_last_run_failed",
        "1 when the most recent finished run of a type failed.",
        "gauge",
        [({"run_type": t}, 0.0 if r.status == "completed" else 1.0) for t, r in last_any.items()],
    )
    metric(
        "garimpo_last_run_products_scraped",
        "Products scraped by the last successful run, by type.",
        "gauge",
        [({"run_type": t}, float(r.products_scraped)) for t, r in last_ok.items()],
    )
    metric(
        "garimpo_last_run_products_failed",
        "Parse or fetch failures in the last successful run, by type.",
        "gauge",
        [({"run_type": t}, float(r.products_failed)) for t, r in last_ok.items()],
    )
    metric(
        "garimpo_last_run_duration_seconds",
        "Duration of the last successful run, by type.",
        "gauge",
        [({"run_type": t}, max(_ts(r.completed_at) - _ts(r.started_at), 0.0)) for t, r in last_ok.items()],
    )

    state = backup.status()
    metric(
        "garimpo_backup_last_success_timestamp_seconds",
        "Time of the last successful backup (0 when none).",
        "gauge",
        [({}, _ts(datetime.fromisoformat(state["last_backup_at"])) if state["last_backup_at"] else 0.0)],
    )
    metric(
        "garimpo_backup_size_bytes",
        "Size of the last backup.",
        "gauge",
        [({}, float(state["last_backup_bytes"] or 0))],
    )
    metric(
        "garimpo_restore_test_ok",
        "1 when the last restore test passed, 0 when it failed or never ran.",
        "gauge",
        [({}, 1.0 if state["last_restore_test_ok"] else 0.0)],
    )
    return "\n".join(lines) + "\n"
