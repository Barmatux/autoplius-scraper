#!/usr/bin/env python3
"""Reuse base filter options when vehicle/year filters are empty."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")

OLD = """    spec_options = fetch_listing_filter_options(path, vehicle_year_filters)
    spec_filters = spec_options.spec_filters("""

NEW = """    has_vehicle_year = (
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
    spec_filters = spec_options.spec_filters("""


def main() -> int:
    text = APP.read_text(encoding="utf-8")
    if "has_vehicle_year" in text:
        print("already patched", APP)
        return 0
    if OLD not in text:
        raise SystemExit("anchor not found")
    APP.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("OK patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
