#!/usr/bin/env python3
"""Upload Volvo listing photos that never made it into MinIO after the disk filled up."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "scraper" / "photo_sync.py").is_file():
    ROOT = Path("/opt/autoplius-scraper")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import connect, init_db, row_to_listing
from scraper.photo_sync import sync_listings_photos
from scraper.s3_storage import is_media_url

VOLVO_MODELS = ("V50", "V60", "V70", "S80", "S60")
YEAR_FROM = 2011


def _is_diesel(fuel: str | None) -> bool:
    text = (fuel or "").lower()
    return "\u0434\u0438\u0437\u0435\u043b" in text or "diesel" in text or "dyzel" in text


def _is_target_title(title: str | None) -> bool:
    words = (title or "").replace(",", " ").replace("-", " ").split()
    if len(words) < 2 or words[0].lower() != "volvo":
        return False
    return words[1].upper() in VOLVO_MODELS


def _needs_photo_sync(item: dict) -> bool:
    urls = [u for u in (item.get("photo_urls") or []) if u]
    if item.get("photo_url") and item["photo_url"] not in urls:
        urls.insert(0, item["photo_url"])
    if not urls:
        return False
    return any(not is_media_url(url) for url in urls)


def load_volvo_listings(db_path: Path) -> list[dict]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM listings
            WHERE (status IS NULL OR status = 'active')
            ORDER BY autoplius_id
            """
        ).fetchall()
    listings = []
    for row in rows:
        item = row_to_listing(row)
        if not _is_target_title(item.get("title")):
            continue
        try:
            year = int(str(item.get("year") or "0")[:4])
        except ValueError:
            year = 0
        if year and year < YEAR_FROM:
            continue
        if not _is_diesel(item.get("fuel")):
            continue
        listings.append(item)
    return listings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats-only", action="store_true", help="Print counts and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    settings = Settings.from_env()
    all_volvo = load_volvo_listings(settings.db_path)
    pending_detail = [item for item in all_volvo if not item.get("detail_scraped")]
    empty_photos = [
        item
        for item in all_volvo
        if not (item.get("photo_urls") or []) and not item.get("photo_url")
    ]
    to_sync = [item for item in all_volvo if _needs_photo_sync(item)]

    print(
        f"volvo_target={len(all_volvo)} pending_detail={len(pending_detail)} "
        f"empty_photos={len(empty_photos)} need_minio_sync={len(to_sync)}",
        flush=True,
    )
    if args.stats_only or not to_sync:
        if not to_sync:
            print("nothing to sync", flush=True)
        return 0

    result = sync_listings_photos(settings, to_sync, log_each=True)
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
