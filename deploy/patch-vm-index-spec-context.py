#!/usr/bin/env python3
"""Add spec filter context and imports required by VM index.html."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")

SPEC_IMPORTS = """from autoplius.spec_filters import (
    build_spec_filter_options,
    build_transmission_raw_values,
    filter_by_body_types,
    filter_by_fuel_types,
    filter_by_transmissions,
    filter_by_volume_range,
    parse_multi_param_values,
    parse_volume_param,
)
from autoplius.transmission_labels import parse_transmission_filter_values
"""

INDEX_INSERT = """    selected_body_types = parse_multi_param_values(request.args.getlist("body_type"))
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

"""

RENDER_INSERT = """        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
        spec_filters=spec_filters,
        volume_from=volume_from_str,
        volume_to=volume_to_str,
"""


def main() -> int:
    text = APP.read_text(encoding="utf-8")

    if "from autoplius.spec_filters import" not in text:
        anchor = "from autoplius.price_display import"
        text = text.replace(anchor, SPEC_IMPORTS + anchor, 1)

    if "spec_filters = build_spec_filter_options" not in text:
        anchor = "    filtered = _filter_by_cities(filtered, selected_cities)\n"
        if anchor not in text:
            raise SystemExit("index city filter anchor not found")
        text = text.replace(anchor, anchor + INDEX_INSERT, 1)

    if "spec_filters=spec_filters" not in text:
        anchor = "        selected_cities=selected_cities,\n"
        if anchor not in text:
            raise SystemExit("render_template anchor not found")
        text = text.replace(anchor, anchor + RENDER_INSERT, 1)

    APP.write_text(text, encoding="utf-8")
    print("OK patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
