#!/usr/bin/env python3
"""List or re-enrich active listings that have no stored photos."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import connect, init_db


def missing_photo_ids(db_path: Path) -> list[int]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT autoplius_id FROM listings
            WHERE (status IS NULL OR status = 'active')
              AND (photo_url IS NULL OR photo_url = '')
              AND (photo_urls_json IS NULL OR photo_urls_json = '[]')
            ORDER BY autoplius_id
            """
        ).fetchall()
    return [int(row["autoplius_id"]) for row in rows]


def thin_gallery_ids(db_path: Path, *, max_photos: int = 1) -> list[int]:
    """Active listings with a suspiciously small gallery (often only list thumb)."""
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT autoplius_id, photo_url, photo_urls_json
            FROM listings
            WHERE (status IS NULL OR status = 'active')
            ORDER BY autoplius_id
            """
        ).fetchall()
    ids: list[int] = []
    for row in rows:
        urls: list[str] = []
        raw = row["photo_urls_json"] or "[]"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            urls = [u for u in parsed if u]
        if row["photo_url"] and row["photo_url"] not in urls:
            urls.insert(0, row["photo_url"])
        if 0 < len(urls) <= max_photos:
            ids.append(int(row["autoplius_id"]))
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--re-enrich",
        action="store_true",
        help="Run tools/re_enrich_listings.py with --sync-photos for missing IDs",
    )
    parser.add_argument(
        "--include-thin",
        action="store_true",
        help="Also include active listings with only 1 stored photo (list thumb)",
    )
    parser.add_argument(
        "--force-photos",
        action="store_true",
        help="Pass --force-photos to re-enrich (overwrite MinIO objects)",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    listing_ids = missing_photo_ids(settings.db_path)
    print(f"missing_photos={len(listing_ids)}")
    if args.include_thin:
        thin_ids = thin_gallery_ids(settings.db_path)
        thin_only = [listing_id for listing_id in thin_ids if listing_id not in set(listing_ids)]
        print(f"thin_galleries={len(thin_only)}")
        listing_ids = sorted(set(listing_ids) | set(thin_only))
    if not listing_ids:
        return
    print(" ".join(str(listing_id) for listing_id in listing_ids))
    if not args.re_enrich:
        return

    cmd = [
        sys.executable,
        str(ROOT / "tools" / "re_enrich_listings.py"),
        *[str(listing_id) for listing_id in listing_ids],
        "--sync-photos",
    ]
    if args.force_photos:
        cmd.append("--force-photos")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
