#!/usr/bin/env python3
"""Deploy SQL listing filters + engine_liters column + index SQL pagination."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
DB = ROOT / "scraper/db.py"
APP = ROOT / "ui/app.py"


def patch_db(text: str) -> str:
    if "engine_liters" not in text:
        needle = '    if "manual_overrides_json" not in cols:\n        conn.execute("ALTER TABLE listings ADD COLUMN manual_overrides_json TEXT")'
        insert = needle + '\n    if "engine_liters" not in cols:\n        conn.execute("ALTER TABLE listings ADD COLUMN engine_liters REAL")\n        conn.execute(\n            "CREATE INDEX IF NOT EXISTS idx_listings_engine_liters ON listings(engine_liters)"\n        )'
        if needle not in text:
            raise SystemExit("db migration anchor not found")
        text = text.replace(needle, insert, 1)

    if '"engine_liters"' not in text:
        needle = '"detail_error": item.get("detail_error"),\n        "status":'
        insert = (
            '"detail_error": item.get("detail_error"),\n'
            '        "engine_liters": engine_volume_liters(item),\n'
            '        "status":'
        )
        if needle not in text:
            raise SystemExit("_listing_row anchor not found")
        text = text.replace(needle, insert, 1)

    if "engine_liters = :engine_liters" not in text:
        text = text.replace(
            "                detail_error = :detail_error,\n                status = :status,",
            "                detail_error = :detail_error,\n                engine_liters = :engine_liters,\n                status = :status,",
            1,
        )
        text = text.replace(
            "            detail_scraped, detail_error, status, archived_at,\n            first_seen_at, last_seen_at, last_run_id, updated_at\n        ) VALUES (",
            "            detail_scraped, detail_error, engine_liters, status, archived_at,\n            first_seen_at, last_seen_at, last_run_id, updated_at\n        ) VALUES (",
            1,
        )
        text = text.replace(
            "            :detail_scraped, :detail_error, :status, :archived_at,\n            :seen_at, :seen_at, :last_run_id, :updated_at",
            "            :detail_scraped, :detail_error, :engine_liters, :status, :archived_at,\n            :seen_at, :seen_at, :last_run_id, :updated_at",
            1,
        )

    if "engine_liters" not in text.split("def row_to_listing", 1)[1].split("def fetch_listings", 1)[0]:
        needle = '"detail_scraped": bool(row["detail_scraped"]) if "detail_scraped" in keys else False,\n        "detail_error":'
        insert = (
            '"detail_scraped": bool(row["detail_scraped"]) if "detail_scraped" in keys else False,\n'
            '        "engine_liters": row["engine_liters"] if "engine_liters" in keys else None,\n'
            '        "detail_error":'
        )
        text = text.replace(needle, insert, 1)

    return text


def patch_app(text: str) -> str:
    if "ListingFilters" in text and "fetch_listing_ids" in text:
        print("app.py already patched")
        return text

    if "from dataclasses import replace" not in text:
        text = text.replace(
            "from __future__ import annotations\n\nimport json",
            "from __future__ import annotations\n\nfrom dataclasses import replace\nimport json",
            1,
        )

    if "from scraper.listing_query import" not in text:
        text = text.replace(
            "from scraper.s3_storage import get_s3_client\n",
            "from scraper.listing_query import (\n"
            "    backfill_engine_liters,\n"
            "    count_listings,\n"
            "    fetch_listing_ids,\n"
            "    fetch_listings_for_options,\n"
            ")\n"
            "from scraper.listing_sql_filters import ListingFilters\n"
            "from scraper.s3_storage import get_s3_client\n",
            1,
        )

    helper = '''

def _listing_filters_for_tab(
    *,
    q: str,
    min_price: int | None,
    max_price: int | None,
    sort: str,
    tab: str,
    upto_19l: bool,
    passable: bool,
    over_3y: bool,
) -> ListingFilters:
    return ListingFilters(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        listing_status="archived" if tab == TAB_ARCHIVED else "active",
        older_than_3_only=over_3y,
        passable_only=passable,
        engine_volume_missing=tab == TAB_NO_VOLUME,
        engine_upto_liters=1.9 if upto_19l and tab != TAB_NO_VOLUME else None,
        catalog_filter=tab != TAB_NO_VOLUME,
        exclude_blocked_makes=True,
    )
'''

    if "_listing_filters_for_tab" not in text:
        anchor = "def _fetch_index_listings("
        text = text.replace(anchor, helper + "\n" + anchor, 1)

    old_index_block = '''    stats = db_stats(path)
    filtered = _fetch_index_listings(
        path,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        tab=tab,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
        profile="filter",
    )
    vehicle_rows = parse_vehicle_filter_rows(
        [value.strip() for value in request.args.getlist("make")],
        [value.strip() for value in request.args.getlist("model")],
    )
    year_from = parse_optional_year(request.args.get("year_from"))
    year_to = parse_optional_year(request.args.get("year_to"))
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from

    make_model_options = build_make_model_options(filtered)
    year_options = build_year_options(filtered)
    vehicle_rows = sanitize_vehicle_rows(vehicle_rows, make_model_options)

    selected_cities = _selected_cities()
    selected_body_types = parse_multi_param_values(request.args.getlist("body_type"))
    selected_fuels = parse_multi_param_values(request.args.getlist("fuel"))
    selected_transmissions = parse_transmission_filter_values(request.args.getlist("transmission"))
    volume_from_str = request.args.get("volume_from", "").strip()
    volume_to_str = request.args.get("volume_to", "").strip()
    volume_from_raw = parse_volume_param(volume_from_str)
    volume_to_raw = parse_volume_param(volume_to_str)
    if volume_from_raw is not None and volume_to_raw is not None and volume_from_raw > volume_to_raw:
        volume_from_raw, volume_to_raw = volume_to_raw, volume_from_raw
        volume_from_str, volume_to_str = volume_to_str, volume_from_str

    city_options = _city_options(filtered)
    filtered = filter_by_vehicle_rows(filtered, vehicle_rows)
    filtered = filter_by_year(filtered, year_from=year_from, year_to=year_to)

    spec_source = filtered
    spec_filters = build_spec_filter_options(
        spec_source,
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
    )
    transmission_raw_values = build_transmission_raw_values(spec_source)

    filtered = _filter_by_cities(filtered, selected_cities)
    filtered = filter_by_body_types(filtered, selected_body_types)
    filtered = filter_by_fuel_types(filtered, selected_fuels)
    filtered = filter_by_transmissions(filtered, selected_transmissions, transmission_raw_values)
    filtered = filter_by_volume_range(filtered, volume_from_raw, volume_to_raw)

    total_in_db = int(stats.get("active_listings") or stats.get("listings") or 0)
    archived_count = int(stats.get("archived_listings") or 0)
    total_filtered = len(filtered)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    page_ids = [item["autoplius_id"] for item in filtered[start : start + PAGE_SIZE]]
    listings = fetch_listings_by_ids(path, page_ids, lite=True)'''

    new_index_block = '''    stats = db_stats(path)
    base_filters = _listing_filters_for_tab(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        tab=tab,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
    )
    vehicle_rows = parse_vehicle_filter_rows(
        [value.strip() for value in request.args.getlist("make")],
        [value.strip() for value in request.args.getlist("model")],
    )
    year_from = parse_optional_year(request.args.get("year_from"))
    year_to = parse_optional_year(request.args.get("year_to"))
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from

    option_pool = fetch_listings_for_options(path, base_filters)
    make_model_options = build_make_model_options(option_pool)
    year_options = build_year_options(option_pool)
    vehicle_rows = sanitize_vehicle_rows(vehicle_rows, make_model_options)

    selected_cities = _selected_cities()
    selected_body_types = parse_multi_param_values(request.args.getlist("body_type"))
    selected_fuels = parse_multi_param_values(request.args.getlist("fuel"))
    selected_transmissions = parse_transmission_filter_values(request.args.getlist("transmission"))
    volume_from_str = request.args.get("volume_from", "").strip()
    volume_to_str = request.args.get("volume_to", "").strip()
    volume_from_raw = parse_volume_param(volume_from_str)
    volume_to_raw = parse_volume_param(volume_to_str)
    if volume_from_raw is not None and volume_to_raw is not None and volume_from_raw > volume_to_raw:
        volume_from_raw, volume_to_raw = volume_to_raw, volume_from_raw
        volume_from_str, volume_to_str = volume_to_str, volume_from_str

    city_options = _city_options(option_pool)
    vehicle_year_filters = replace(
        base_filters,
        vehicle_rows=vehicle_rows,
        year_from=year_from,
        year_to=year_to,
    )
    spec_source = fetch_listings_for_options(path, vehicle_year_filters)
    spec_filters = build_spec_filter_options(
        spec_source,
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
    )
    transmission_raw_values = build_transmission_raw_values(spec_source)
    transmission_values = transmission_db_values_for_slugs(
        transmission_raw_values,
        selected_transmissions,
    )

    selected_filters = replace(
        vehicle_year_filters,
        cities=selected_cities,
        body_types=selected_body_types,
        fuels=selected_fuels,
        transmissions=transmission_values,
        volume_from=volume_from_raw,
        volume_to=volume_to_raw,
    )

    total_in_db = int(stats.get("active_listings") or stats.get("listings") or 0)
    archived_count = int(stats.get("archived_listings") or 0)
    total_filtered = count_listings(path, selected_filters)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    page_ids = fetch_listing_ids(
        path,
        selected_filters,
        limit=PAGE_SIZE,
        offset=start,
    )
    listings = fetch_listings_by_ids(path, page_ids, lite=True)'''

    if old_index_block not in text:
        raise SystemExit("index() block not found")
    text = text.replace(old_index_block, new_index_block, 1)

    if "transmission_db_values_for_slugs," not in text:
        text = text.replace(
            "from autoplius.transmission_labels import parse_transmission_filter_values\n",
            "from autoplius.transmission_labels import (\n"
            "    parse_transmission_filter_values,\n"
            "    transmission_db_values_for_slugs,\n"
            ")\n",
            1,
        )

    return text


def main() -> int:
    db_text = patch_db(DB.read_text(encoding="utf-8"))
    DB.write_text(db_text, encoding="utf-8")
    print("OK patched", DB)

    app_text = patch_app(APP.read_text(encoding="utf-8"))
    APP.write_text(app_text, encoding="utf-8")
    print("OK patched", APP)

    import sys

    sys.path.insert(0, str(ROOT))
    from scraper.config import Settings
    from scraper.listing_query import backfill_engine_liters

    updated = backfill_engine_liters(Settings.from_env().db_path)
    print("OK backfilled engine_liters:", updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
