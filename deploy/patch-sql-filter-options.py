#!/usr/bin/env python3
"""Switch index() filter dropdowns from full row scan to SQL aggregations."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
APP = ROOT / "ui/app.py"


def patch_app(text: str) -> str:
    if "fetch_listing_filter_options" in text:
        print("app.py already patched for SQL filter options")
        return text

    if "from scraper.listing_filter_options import fetch_listing_filter_options\n" not in text:
        text = text.replace(
            "from scraper.listing_sql_filters import ListingFilters\n",
            "from scraper.listing_filter_options import fetch_listing_filter_options\n"
            "from scraper.listing_sql_filters import ListingFilters\n",
            1,
        )

    old_block = """    option_pool = fetch_listings_for_options(path, base_filters)
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
    )"""

    new_block = """    base_options = fetch_listing_filter_options(path, base_filters)
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
    )"""

    if old_block not in text:
        raise SystemExit("index() options block not found")
    return text.replace(old_block, new_block, 1)


def main() -> int:
    text = patch_app(APP.read_text(encoding="utf-8"))
    APP.write_text(text, encoding="utf-8")
    print("OK patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
