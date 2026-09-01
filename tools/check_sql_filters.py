#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters

path = Settings.from_env().db_path
base = ListingFilters(sort="added_desc")
print("active", count_listings(path, base))
upto19 = ListingFilters(
    sort="added_desc",
    engine_upto_liters=1.9,
    catalog_filter=True,
    exclude_blocked_makes=True,
)
print("upto19", count_listings(path, upto19))
passable = ListingFilters(sort="added_desc", passable_only=True, catalog_filter=True)
print("passable", count_listings(path, passable))
print("sample", fetch_listing_ids(path, base, limit=3))
