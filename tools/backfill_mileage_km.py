#!/usr/bin/env python3
"""Backfill mileage_km from parameters_json for listings with empty mileage."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.listing_query import backfill_mileage_km


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Recompute even when mileage_km is set")
    args = parser.parse_args()
    updated = backfill_mileage_km(Settings.from_env().db_path, force=args.force)
    print(f"backfill_mileage_km={updated}")


if __name__ == "__main__":
    main()
