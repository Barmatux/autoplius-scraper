#!/usr/bin/env python3
"""Ensure transmission_db_values_for_slugs is imported in ui/app.py."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")


def main() -> int:
    text = APP.read_text(encoding="utf-8")
    if "transmission_db_values_for_slugs" in text.split("def index", 1)[0]:
        print("already ok", APP)
        return 0

    old = "from autoplius.transmission_labels import parse_transmission_filter_values, transmission_listing_label\n"
    new = (
        "from autoplius.transmission_labels import (\n"
        "    parse_transmission_filter_values,\n"
        "    transmission_db_values_for_slugs,\n"
        "    transmission_listing_label,\n"
        ")\n"
    )
    if old not in text:
        old2 = "from autoplius.transmission_labels import parse_transmission_filter_values\n"
        new2 = (
            "from autoplius.transmission_labels import (\n"
            "    parse_transmission_filter_values,\n"
            "    transmission_db_values_for_slugs,\n"
            ")\n"
        )
        if old2 in text:
            text = text.replace(old2, new2, 1)
        else:
            raise SystemExit("transmission_labels import anchor not found")
    else:
        text = text.replace(old, new, 1)

    APP.write_text(text, encoding="utf-8")
    print("OK patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
