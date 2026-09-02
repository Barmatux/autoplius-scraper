#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.listing_query import backfill_engine_liters

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill listings.engine_liters from parsed specs.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalculate engine_liters for all listings, not only NULL rows.",
    )
    args = parser.parse_args()
    updated = backfill_engine_liters(Settings.from_env().db_path, force=args.force)
    print("backfilled", updated)
