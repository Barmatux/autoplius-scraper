#!/usr/bin/env python3
"""List or re-enrich active listings that have no stored photos."""
from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--re-enrich",
        action="store_true",
        help="Run tools/re_enrich_listings.py with --sync-photos for missing IDs",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    listing_ids = missing_photo_ids(settings.db_path)
    print(f"missing_photos={len(listing_ids)}")
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
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
