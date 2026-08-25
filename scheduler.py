#!/usr/bin/env python3
"""Hourly Autoplius scraper daemon (test mode by default)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scraper.config import Settings
from scraper.job import run_job
from scraper.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def _run_once(settings: Settings) -> None:
    started = datetime.now(timezone.utc).isoformat()
    logger.info("Scheduled run started at %s", started)
    try:
        result = run_job(settings)
        logger.info(
            "Scheduled run finished: %s listings, diff=%s",
            result.payload["listing_count"],
            result.diff,
        )
    except Exception as exc:
        logger.error("Scheduled run failed: %s", exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autoplius hourly scraper scheduler")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run immediately and exit (no scheduler loop)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    setup_logging(settings.logs_dir, verbose=args.verbose)

    if args.run_once:
        _run_once(settings)
        return 0

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _run_once,
        trigger=IntervalTrigger(hours=settings.interval_hours),
        args=[settings],
        id="autoplius_scrape",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    def shutdown(signum, frame):  # noqa: ARG001
        logger.info("Shutdown signal received, stopping scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Scheduler started: every %s hour(s), test_mode=%s, pages=%s",
        settings.interval_hours,
        settings.test_mode,
        settings.pages,
    )
    _run_once(settings)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
