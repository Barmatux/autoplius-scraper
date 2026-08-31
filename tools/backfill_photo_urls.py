#!/usr/bin/env python3
"""Upgrade stored listing photo URLs to full-size CDN links."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.photo_urls import normalize_photo_list
from scraper.db import connect, init_db


def backfill(db_path: Path) -> tuple[int, int]:
    init_db(db_path)
    updated = 0
    checked = 0
    with connect(db_path) as conn:
        rows = conn.execute("SELECT autoplius_id, photo_url, photo_urls_json FROM listings").fetchall()
        for row in rows:
            checked += 1
            old_urls = json.loads(row["photo_urls_json"] or "[]")
            new_urls = normalize_photo_list(old_urls)
            new_cover = new_urls[0] if new_urls else row["photo_url"]
            if new_urls == old_urls and new_cover == row["photo_url"]:
                continue
            conn.execute(
                """
                UPDATE listings
                SET photo_url = ?, photo_urls_json = ?, updated_at = datetime('now')
                WHERE autoplius_id = ?
                """,
                (new_cover, json.dumps(new_urls, ensure_ascii=False), row["autoplius_id"]),
            )
            updated += 1
    return checked, updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    checked, updated = backfill(args.db)
    print(f"Checked {checked} listings, updated {updated}")


if __name__ == "__main__":
    main()
