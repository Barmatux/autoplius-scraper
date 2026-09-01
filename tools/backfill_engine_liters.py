#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.listing_query import backfill_engine_liters

if __name__ == "__main__":
    updated = backfill_engine_liters(Settings.from_env().db_path)
    print("backfilled", updated)
