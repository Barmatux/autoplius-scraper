#!/usr/bin/env python3
"""Run one Autoplius search scrape (pages 1..N, all listings)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from scraper.config import Settings
from scraper.job import run_job
from scraper.logging_setup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Autoplius search + detail pages")
    parser.add_argument("--pages", type=int, help="Override SCRAPE_PAGES")
    parser.add_argument(
        "--enrich",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Fetch full listing detail pages (default: ENRICH_DETAILS)",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        help="Limit how many detail pages to fetch (0 = all)",
    )
    parser.add_argument(
        "--test-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override TEST_MODE (default: true)",
    )
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full scrape (all pages, enrich all listings)",
    )
    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override INCREMENTAL_SCRAPE",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.pages is not None:
        settings = replace(settings, pages=args.pages)
    if args.enrich is not None:
        settings = replace(settings, enrich_details=args.enrich)
    if args.enrich_limit is not None:
        settings = replace(settings, enrich_limit=args.enrich_limit)
    if args.test_mode is not None:
        settings = replace(settings, test_mode=args.test_mode)
    if args.headed:
        settings = replace(settings, headless=False)
    if args.full:
        settings = replace(settings, incremental_scrape=False, enrich_new_only=False)
    if args.incremental is not None:
        settings = replace(settings, incremental_scrape=args.incremental)

    setup_logging(settings.logs_dir, verbose=args.verbose)

    result = run_job(settings)
    print(
        f"OK: {result.payload['listing_count']} listings, "
        f"details={result.payload.get('details_scraped', 0)}, "
        f"snapshot={result.snapshot_path}, diff={result.diff}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
