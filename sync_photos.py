#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import fetch_all_listings
from scraper.photo_sync import sync_listings_photos


def main() -> None:
    parser = argparse.ArgumentParser(description="Download listing photos and upload to MinIO/S3")
    parser.add_argument("--limit", type=int, default=0, help="Limit listings (0 = all)")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout for image download")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload or update DB")
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing objects")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings.from_env()
    if not settings.s3_enabled:
        raise SystemExit("S3 is not configured. Set S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY in .env")

    if not settings.db_path.is_file():
        raise SystemExit(f"Database not found: {settings.db_path}")

    listings = fetch_all_listings(settings.db_path)
    if args.limit and args.limit > 0:
        listings = listings[: args.limit]

    result = sync_listings_photos(
        settings,
        listings,
        timeout=args.timeout,
        dry_run=args.dry_run,
        force=args.force,
        log_each=True,
    )
    logger.info(
        "sync-summary: %s total_listings=%s uploaded_or_planned=%s dry_run=%s force=%s",
        " ".join(f"{key}={value}" for key, value in sorted(result.get("stats", {}).items())),
        result.get("listings", 0),
        result.get("uploaded", 0),
        args.dry_run,
        args.force,
    )


if __name__ == "__main__":
    main()
