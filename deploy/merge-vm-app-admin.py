#!/usr/bin/env python3
"""Restore VM UI app.py from stash snapshot and re-apply admin routes."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")
STASHED = Path("/tmp/stashed_app.py")
ADMIN_BLOCK = Path("/tmp/admin_block.py")


def main() -> int:
    if not STASHED.is_file():
        raise SystemExit(f"missing {STASHED}")
    if not APP.is_file():
        raise SystemExit(f"missing {APP}")

    stashed = STASHED.read_text(encoding="utf-8")
    current = APP.read_text(encoding="utf-8")

    if ADMIN_BLOCK.is_file():
        admin_block = ADMIN_BLOCK.read_text(encoding="utf-8")
    else:
        start = current.index("def _admin_status_filter")
        end = current.index('@app.get("/api/listings")')
        admin_block = current[start:end]
        ADMIN_BLOCK.write_text(admin_block, encoding="utf-8")

    merged = stashed
    if "import json" not in merged.splitlines()[:8]:
        merged = merged.replace("import os\n", "import json\nimport os\n", 1)
    if "update_listing_admin" not in merged:
        merged = merged.replace(
            "    scrape_runs_analytics,\n",
            "    scrape_runs_analytics,\n    update_listing_admin,\n",
            1,
        )
    if "TAB_ADMIN" not in merged:
        merged = merged.replace(
            'TAB_ARCHIVED = "archived"\n',
            'TAB_ARCHIVED = "archived"\nTAB_ADMIN = "admin"\nADMIN_PAGE_SIZE = 50\n',
            1,
        )

    marker = '@app.get("/api/listings")'
    if "def admin_listings" not in merged:
        merged = merged.replace(marker, admin_block + marker, 1)

    APP.write_text(merged, encoding="utf-8")
    print("OK merged", APP)
    print("engine_kpp_lines", "engine_kpp_lines" in merged)
    print("admin_listings", "def admin_listings" in merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
