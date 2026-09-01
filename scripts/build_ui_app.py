#!/usr/bin/env python3
"""Build ui/app.py from VM baseline with SQL index() integrated in git."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_vm_sync" / "app.py"
DST = ROOT / "ui" / "app.py"

LISTING_FILTERS_HELPER = '''

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

OLD_INDEX = """    stats = db_stats(path)
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
        lite=True,
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
    city_options = _city_options(filtered)
    filtered = filter_by_vehicle_rows(filtered, vehicle_rows)
    filtered = filter_by_year(filtered, year_from=year_from, year_to=year_to)
    filtered = _filter_by_cities(filtered, selected_cities)
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

    spec_source = filtered
    spec_filters = build_spec_filter_options(
        spec_source,
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
    )
    transmission_raw_values = build_transmission_raw_values(spec_source)

    filtered = filter_by_body_types(filtered, selected_body_types)
    filtered = filter_by_fuel_types(filtered, selected_fuels)
    filtered = filter_by_transmissions(filtered, selected_transmissions, transmission_raw_values)
    filtered = filter_by_volume_range(filtered, volume_from_raw, volume_to_raw)

    no_volume_count = (
        len(filtered)
        if tab == TAB_NO_VOLUME
        else None
    )

    total_in_db = int(stats.get("active_listings") or stats.get("listings") or 0)
    archived_count = int(stats.get("archived_listings") or 0)
    total_filtered = len(filtered)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    listings = filtered[start : start + PAGE_SIZE]"""

NEW_INDEX = """    stats = db_stats(path)
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

    base_options = fetch_listing_filter_options(path, base_filters)
    make_model_options = base_options.make_model_options
    year_options = base_options.year_options
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

    city_options = base_options.city_options
    vehicle_year_filters = replace(
        base_filters,
        vehicle_rows=vehicle_rows,
        year_from=year_from,
        year_to=year_to,
    )
    has_vehicle_year = (
        year_from is not None
        or year_to is not None
        or any(
            (row.get("make") or "").strip() or (row.get("model") or "").strip()
            for row in vehicle_rows
        )
    )
    spec_options = (
        fetch_listing_filter_options(path, vehicle_year_filters)
        if has_vehicle_year
        else base_options
    )
    spec_filters = spec_options.spec_filters(
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
    )
    transmission_values = transmission_db_values_for_slugs(
        spec_options.transmission_values,
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

    no_volume_count = (
        count_listings(path, ListingFilters(engine_volume_missing=True, catalog_filter=False))
        if tab == TAB_NO_VOLUME
        else None
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
    listings = fetch_listings_by_ids(path, page_ids, lite=True)"""

NO_VOLUME_OLD = """    no_volume_count = len(
        fetch_listings(path, engine_volume_missing=True, passable_only=False)
    )"""

NO_VOLUME_NEW = """    no_volume_count = count_listings(
        path,
        ListingFilters(engine_volume_missing=True, catalog_filter=False),
    )"""

NO_VOLUME_CATALOG_OLD = """    no_volume_count = len(
        fetch_listings(path, engine_volume_missing=True, catalog_filter=False)
    )"""

ADMIN_NO_VOLUME_OLD = """        no_volume_count=len(fetch_listings(path, engine_volume_missing=True, catalog_filter=False)),"""

ADMIN_NO_VOLUME_NEW = """        no_volume_count=count_listings(
            path,
            ListingFilters(engine_volume_missing=True, catalog_filter=False),
        ),"""


def patch(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")

    if "from dataclasses import replace" not in text:
        text = text.replace(
            "from __future__ import annotations\n\nimport json",
            "from __future__ import annotations\n\nfrom dataclasses import replace\nimport json",
            1,
        )

    if "from scraper.listing_query import" not in text:
        text = text.replace(
            "from scraper.s3_storage import get_s3_client\n",
            "from scraper.listing_filter_options import fetch_listing_filter_options\n"
            "from scraper.listing_query import count_listings, fetch_listing_ids\n"
            "from scraper.listing_sql_filters import ListingFilters\n"
            "from scraper.s3_storage import get_s3_client\n",
            1,
        )

    if "fetch_listings_by_ids" not in text.split("from scraper.db import", 1)[1].split(")", 1)[0]:
        text = text.replace(
            "    fetch_listings,\n",
            "    fetch_listings,\n    fetch_listings_by_ids,\n",
            1,
        )

    if "_listing_filters_for_tab" not in text:
        text = text.replace(
            "def _fetch_index_listings(",
            LISTING_FILTERS_HELPER + "\ndef _fetch_index_listings(",
            1,
        )

    if OLD_INDEX not in text:
        raise SystemExit("index() block not found in VM app.py")
    text = text.replace(OLD_INDEX, NEW_INDEX, 1)

    text = text.replace(NO_VOLUME_OLD, NO_VOLUME_NEW)
    text = text.replace(NO_VOLUME_CATALOG_OLD, NO_VOLUME_NEW)
    text = text.replace(ADMIN_NO_VOLUME_OLD, ADMIN_NO_VOLUME_NEW, 1)

    inject_old = """        return {
            "catalog_missing_count": engine_catalog_missing_count(path),
            "catalog_new_count": engine_catalog_new_count(path),
        }"""
    inject_new = """        return {
            "catalog_missing_count": engine_catalog_missing_count(path),
            "catalog_new_count": engine_catalog_new_count(path),
            "no_volume_count": count_listings(
                path,
                ListingFilters(engine_volume_missing=True, catalog_filter=False),
            ),
        }"""
    if inject_old in text and '"no_volume_count": count_listings' not in text.split("def inject_tab_counts", 1)[1].split("def db_path", 1)[0]:
        text = text.replace(inject_old, inject_new, 1)

    return text


def main() -> int:
    text = patch(SRC.read_text(encoding="utf-8-sig"))
    DST.write_text(text, encoding="utf-8")
    print("OK wrote", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
