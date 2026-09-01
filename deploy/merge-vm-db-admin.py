#!/usr/bin/env python3
"""Merge git admin DB helpers into VM stashed db.py snapshot."""
from __future__ import annotations

from pathlib import Path

DB = Path("/opt/autoplius-scraper/scraper/db.py")
STASHED = Path("/tmp/stashed_db.py")
GIT = Path("/tmp/git_db.py")


def extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def main() -> int:
    if not STASHED.is_file():
        raise SystemExit(f"missing {STASHED}")
    if not GIT.is_file():
        raise SystemExit(f"missing {GIT}; run: git show HEAD:scraper/db.py > /tmp/git_db.py")

    stashed = STASHED.read_text(encoding="utf-8")
    git_db = GIT.read_text(encoding="utf-8")

    merged = stashed

    if "manual_overrides_json" not in merged:
        merged = merged.replace(
            '    if "price_vat_note" not in cols:\n'
            '        conn.execute("ALTER TABLE listings ADD COLUMN price_vat_note TEXT")\n',
            '    if "price_vat_note" not in cols:\n'
            '        conn.execute("ALTER TABLE listings ADD COLUMN price_vat_note TEXT")\n'
            '    if "manual_overrides_json" not in cols:\n'
            '        conn.execute("ALTER TABLE listings ADD COLUMN manual_overrides_json TEXT")\n',
            1,
        )

    if "encode_manual_overrides" not in merged:
        merged = merged.replace(
            "from scraper.listing_sync import (\n    LISTING_STATUS_ACTIVE,\n"
            "    LISTING_STATUS_ARCHIVED,\n    merge_listing_row,\n)",
            "from scraper.listing_sync import (\n    ADMIN_EDITABLE_FIELDS,\n"
            "    LISTING_STATUS_ACTIVE,\n    LISTING_STATUS_ARCHIVED,\n"
            "    encode_manual_overrides,\n    merge_listing_row,\n"
            "    parse_manual_overrides,\n)",
            1,
        )

    if "manual_overrides_json = :manual_overrides_json" not in merged:
        merged = merged.replace(
            "                archived_at = :archived_at,\n"
            "                last_seen_at = :last_seen_at,\n",
            "                archived_at = :archived_at,\n"
            "                manual_overrides_json = :manual_overrides_json,\n"
            "                last_seen_at = :last_seen_at,\n",
            1,
        )

    if '"manual_overrides": parse_manual_overrides' not in merged:
        merged = merged.replace(
            '        "last_run_id": row["last_run_id"] if "last_run_id" in keys else None,\n    }',
            '        "last_run_id": row["last_run_id"] if "last_run_id" in keys else None,\n'
            '        "updated_at": row["updated_at"] if "updated_at" in keys else None,\n'
            '        "manual_overrides": parse_manual_overrides(\n'
            '            row["manual_overrides_json"] if "manual_overrides_json" in keys else None\n'
            "        ),\n    }",
            1,
        )

    if "catalog_filter: bool = True" not in merged and "def fetch_listings(" in merged:
        merged = merged.replace(
            "    lite: bool = False,\n) -> list[dict[str, Any]]:",
            "    lite: bool = False,\n    catalog_filter: bool = True,\n) -> list[dict[str, Any]]:",
            1,
        )
        merged = merged.replace(
            "    listings = [item for item in listings if is_catalog_visible(item)]\n    return listings",
            "    if catalog_filter:\n"
            "        listings = [item for item in listings if is_catalog_visible(item)]\n"
            "    return listings",
            1,
        )

    if "def update_listing_admin(" not in merged:
        admin_block = extract_block(git_db, "def _optional_int(", "def set_listing_archived(")
        archive_block = extract_block(git_db, "def set_listing_archived(", "def db_stats(")
        merged = merged.replace("def db_stats(", admin_block + archive_block + "def db_stats(", 1)
    elif "def set_listing_archived(" not in merged:
        archive_block = extract_block(git_db, "def set_listing_archived(", "def db_stats(")
        merged = merged.replace("def db_stats(", archive_block + "def db_stats(", 1)

    DB.write_text(merged, encoding="utf-8")
    print("OK merged db", DB)
    print("fetch_engine_catalog", "def fetch_engine_catalog(" in merged)
    print("update_listing_admin", "def update_listing_admin(" in merged)
    print("set_listing_archived", "def set_listing_archived(" in merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
