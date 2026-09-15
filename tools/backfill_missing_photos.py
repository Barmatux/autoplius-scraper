#!/usr/bin/env python3
"""List or re-enrich active listings that have no / thin stored photo galleries."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import (
    connect,
    init_db,
    listing_photo_count,
    listing_select_columns,
    load_thin_gallery_ids,
    row_to_listing,
)
from scraper.sql_dialect import listings_source_clause


def missing_photo_ids(db_path: Path) -> list[int]:
    init_db(db_path)
    columns = listing_select_columns("lite")
    source = listings_source_clause()
    where = "WHERE COALESCE(status, 'active') = 'active'"
    if source:
        where = f"WHERE {source} AND COALESCE(status, 'active') = 'active'"
    with connect(db_path) as conn:
        rows = conn.execute(f"SELECT {columns} FROM listings {where}").fetchall()
    ids: list[int] = []
    for row in rows:
        listing = row_to_listing(row)
        if listing_photo_count(listing) == 0:
            ids.append(int(listing["autoplius_id"]))
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
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap on IDs to re-enrich (0 = all)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default="",
        help="Optional comma/space-separated listing IDs to force into the batch",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    listing_ids = missing_photo_ids(settings.db_path)
    print(f"missing_photos={len(listing_ids)}")
    if args.include_thin:
        thin_ids = sorted(load_thin_gallery_ids(settings.db_path, max_photos=1))
        thin_only = [listing_id for listing_id in thin_ids if listing_id not in set(listing_ids)]
        print(f"thin_galleries={len(thin_only)}")
        listing_ids = sorted(set(listing_ids) | set(thin_only))

    forced: list[int] = []
    if args.ids.strip():
        for part in args.ids.replace(",", " ").split():
            part = part.strip()
            if part.isdigit():
                forced.append(int(part))
        if forced:
            print(f"forced_ids={len(forced)}")

    # Keep forced IDs first so --limit cannot drop the ones we care about.
    rest = [listing_id for listing_id in listing_ids if listing_id not in set(forced)]
    listing_ids = list(dict.fromkeys([*forced, *rest]))
    if args.limit > 0:
        listing_ids = listing_ids[: args.limit]
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
