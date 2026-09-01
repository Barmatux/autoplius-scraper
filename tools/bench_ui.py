#!/usr/bin/env python3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import db_stats, fetch_listings_by_ids
from scraper.listing_filter_options import fetch_listing_filter_options
from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters

s = Settings.from_env()
filters = ListingFilters(
    sort="added_desc",
    engine_upto_liters=1.9,
    catalog_filter=True,
    exclude_blocked_makes=True,
)

t0 = time.perf_counter()
stats = db_stats(s.db_path)
t1 = time.perf_counter()
options = fetch_listing_filter_options(s.db_path, filters)
t2 = time.perf_counter()
total = count_listings(s.db_path, filters)
t3 = time.perf_counter()
page_ids = fetch_listing_ids(s.db_path, filters, limit=50)
t4 = time.perf_counter()
page = fetch_listings_by_ids(s.db_path, page_ids, lite=True)
t5 = time.perf_counter()

print("active_listings", stats.get("active_listings"))
print("db_stats_sec", round(t1 - t0, 3))
print("options_sec", round(t2 - t1, 3))
print("cities", len(options.city_options), "makes", len(options.make_model_options.get("makes") or []))
print("count_sec", round(t3 - t2, 3), "filtered", total)
print("ids_sec", round(t4 - t3, 3))
print("page_sec", round(t5 - t4, 3), "rows", len(page))
print("total_sec", round(t5 - t0, 3))
