#!/usr/bin/env python3
"""Add engine_liters to _listing_row and upsert SQL if missing."""
from __future__ import annotations

from pathlib import Path

DB = Path("/opt/autoplius-scraper/scraper/db.py")


def main() -> int:
    text = DB.read_text(encoding="utf-8")
    changed = False

    needle = '"detail_error": item.get("detail_error"),\n        "status":'
    insert = (
        '"detail_error": item.get("detail_error"),\n'
        '        "engine_liters": engine_volume_liters(item),\n'
        '        "status":'
    )
    if insert not in text and needle in text:
        text = text.replace(needle, insert, 1)
        changed = True

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
        changed = True

    if changed:
        DB.write_text(text, encoding="utf-8")
        print("OK patched", DB)
    else:
        print("already patched", DB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
