"""Background scheduler for recurring jobs (APScheduler)

Purpose
-------
Run lightweight, recurring jobs without a separate worker stack. This is a
simple and dev-friendly way to kick off nightly fundamentals ingestion and
daily price rollups. If you later need horizontal scale or heavy tasks, you
can move these to a distributed queue (Celery/Arq/RQ) with minimal changes.

How it works
------------
- `start_scheduler(tz)` creates a BackgroundScheduler in the provided timezone.
- We add two Cron jobs:
    * 03:00 → `nightly_fundamentals_job` (fetch EDGAR companyfacts, transform, upsert)
    * 04:00 → `daily_prices_job` (fetch daily prices, roll up to FY, upsert)
- The FastAPI app calls `start_scheduler()` on startup (see `app/api/main.py`).
- On shutdown we stop the scheduler to avoid orphaned threads.

Notes
-----
- Jobs are **placeholders** here; wire them to your ETL once ready.
- Keep jobs idempotent and rate-limited (be polite to SEC and any vendors).
- Use structured logging so you can trace runs in production.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)


# -----------------------------
# Job functions (stubs)
# -----------------------------

def nightly_fundamentals_job() -> None:
    """Placeholder: pull EDGAR fundamentals for tracked companies.

    Suggested flow:
    1) Query companies where `is_tracked = true`.
    2) For each company: fetch `companyfacts` → select tags → normalize → upsert
       into `financials_annual` and write `fact_provenance`.
    3) Recompute per-year metrics for any updated years.
    """
    log.info("[jobs] nightly_fundamentals_job start")
    # TODO: call your ingest pipeline here
    log.info("[jobs] nightly_fundamentals_job done")


def daily_prices_job() -> None:
    """Placeholder: fetch daily adjusted prices and roll up to fiscal years."""
    log.info("[jobs] daily_prices_job start")
    # TODO: fetch prices for tracked tickers; roll to FY; upsert `prices_annual`
    log.info("[jobs] daily_prices_job done")


# -----------------------------
# Scheduler lifecycle
# -----------------------------

def start_scheduler(tz: str = "America/New_York") -> BackgroundScheduler:
    """Create and start a background scheduler with two cron jobs.

    Args:
        tz: IANA timezone string (e.g., 'America/New_York').

    Returns:
        Running `BackgroundScheduler` instance (so the caller can shut it down).
    """
    sched = BackgroundScheduler(timezone=tz)

    # Nightly fundamentals at 03:00
    sched.add_job(
        nightly_fundamentals_job,
        CronTrigger(hour=3, minute=0),
        id="nightly_fundamentals",
        replace_existing=True,
    )

    # Daily prices at 04:00
    sched.add_job(
        daily_prices_job,
        CronTrigger(hour=4, minute=0),
        id="daily_prices",
        replace_existing=True,
    )

    sched.start()
    log.info("[jobs] scheduler started with timezone=%s", tz)
    return sched
