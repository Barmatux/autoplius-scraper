#!/usr/bin/env python3
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import db_stats, fetch_listings_by_ids
from scraper.listing_filter_options import fetch_listing_filter_options
from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters

path = Settings.from_env().db_path
base_filters = ListingFilters(
    sort="added_desc",
    engine_upto_liters=1.9,
    catalog_filter=True,
    exclude_blocked_makes=True,
)
vehicle_year_filters = replace(base_filters)

t0 = time.perf_counter()
stats = db_stats(path)
t1 = time.perf_counter()
base_options = fetch_listing_filter_options(path, base_filters)
t2 = time.perf_counter()
spec_options = fetch_listing_filter_options(path, vehicle_year_filters)
t3 = time.perf_counter()
total = count_listings(path, base_filters)
t4 = time.perf_counter()
page_ids = fetch_listing_ids(path, base_filters, limit=50)
t5 = time.perf_counter()
page = fetch_listings_by_ids(path, page_ids, lite=True)
t6 = time.perf_counter()

print("db_stats", round(t1 - t0, 3))
print("base_options", round(t2 - t1, 3))
print("spec_options", round(t3 - t2, 3))
print("count", round(t4 - t3, 3))
print("ids", round(t5 - t4, 3))
print("page", round(t6 - t5, 3))
print("total", round(t6 - t0, 3))
print("rows", len(page))
