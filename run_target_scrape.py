#!/usr/bin/env python3
"""Deep scrape of Roman's target models (all pages, filtered queries)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from autoplius.target_queries import build_target_queries, query_summary
from scraper.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scrape all Autoplius listings for configured target models",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=500,
        help="Max pages per query (default: 500, stops earlier on empty page)",
    )
    parser.add_argument(
        "--list-queries",
        action="store_true",
        help="Print planned search queries and exit",
    )
    parser.add_argument(
        "--discover-ids",
        action="store_true",
        help="Run tools/discover_catalog_ids.py first",
    )
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip detail pages (search preview only)",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        default=0,
        help="Limit detail pages (0 = all found listings)",
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Skip search; enrich listings without detail_scraped in DB",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent
    if args.discover_ids:
        from tools.discover_catalog_ids import main as discover_main

        discover_main()

    queries = build_target_queries(root=root)
    if args.list_queries:
        print(json.dumps(query_summary(queries), ensure_ascii=False, indent=2))
        return 0

    from scraper.logging_setup import setup_logging

    settings = Settings.from_env(root=root)
    target_detail_delay = float(os.environ.get("TARGET_DETAIL_DELAY_SEC", "0") or "0")
    target_page_delay = float(os.environ.get("TARGET_PAGE_DELAY_SEC", "0") or "0")
    detail_delay_sec = (
        target_detail_delay if target_detail_delay > 0 else settings.detail_delay_sec
    )
    page_delay_sec = target_page_delay if target_page_delay > 0 else settings.page_delay_sec
    settings = replace(
        settings,
        test_mode=False,
        pages=args.pages,
        incremental_scrape=False,
        enrich_new_only=False,
        enrich_details=not args.no_enrich,
        enrich_limit=args.enrich_limit,
        archive_removed_on_full_scrape=False,
        search_newest_first=False,
        headless=not args.headed,
        detail_delay_sec=detail_delay_sec,
        page_delay_sec=page_delay_sec,
    )

    setup_logging(settings.logs_dir, verbose=args.verbose)

    from scraper.job import scrape_search_pages

    if args.enrich_only:
        print("Starting target enrich-only resume (pending detail listings)", file=sys.stderr)
    else:
        print(f"Starting target scrape: {len(queries)} queries", file=sys.stderr)
        for query in queries:
            print(f"  - {query.label}", file=sys.stderr)

    result = scrape_search_pages(
        settings,
        queries=queries if not args.enrich_only else None,
        enrich_only=args.enrich_only,
    )
    payload = result.payload
    print(
        f"OK: {payload['listing_count']} listings, "
        f"details={payload.get('details_scraped', 0)}, "
        f"snapshot={result.snapshot_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
