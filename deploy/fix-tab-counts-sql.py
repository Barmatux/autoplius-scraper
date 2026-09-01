#!/usr/bin/env python3
"""Use SQL count for no_volume tab badge instead of loading all listings."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")

OLD = """            "no_volume_count": len(
                fetch_listings(path, engine_volume_missing=True, catalog_filter=False)
            ),"""

NEW = """            "no_volume_count": count_listings(
                path,
                ListingFilters(engine_volume_missing=True, catalog_filter=False),
            ),"""


def main() -> int:
    text = APP.read_text(encoding="utf-8")
    if "count_listings(\n                path,\n                ListingFilters(engine_volume_missing=True" in text:
        print("already patched", APP)
        return 0
    if OLD not in text:
        raise SystemExit("inject_tab_counts anchor not found")
    APP.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("OK patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
