#!/usr/bin/env python3
from pathlib import Path

DB = Path("/opt/autoplius-scraper/scraper/db.py")
text = DB.read_text(encoding="utf-8")
old = '''LISTING_COLUMNS_FILTER = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, has_vin_badge, parameters_json, "
    "description, description_ru, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)
LISTING_COLUMNS_LITE = LISTING_COLUMNS_FILTER + ", photo_urls_json"'''
new = '''LISTING_COLUMNS_FILTER = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, has_vin_badge, parameters_json, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)
LISTING_COLUMNS_LITE = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, photo_urls_json, has_vin_badge, parameters_json, "
    "description, description_ru, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)'''
if old not in text:
    if "photo_urls_json, has_vin_badge, parameters_json," in text and "LISTING_COLUMNS_LITE = (" in text:
        print("columns already updated")
    else:
        raise SystemExit("column block not found")
else:
    DB.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("OK updated listing columns")
