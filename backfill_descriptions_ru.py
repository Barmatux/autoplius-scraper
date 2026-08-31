#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.translate import is_translation_error, translate_to_russian
from scraper.config import Settings
from scraper.config import Settings
from scraper.db import connect, init_db, _utc_now

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Russian descriptions for existing listings")
    parser.add_argument("--limit", type=int, default=0, help="Limit listings (0 = all missing)")
    parser.add_argument("--force", action="store_true", help="Re-translate even if description_ru exists")
    parser.add_argument(
        "--repair-errors",
        action="store_true",
        help="Re-translate rows where description_ru contains translator error text",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    init_db(settings.db_path)

    with connect(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT autoplius_id, description, description_ru FROM listings "
            "WHERE description IS NOT NULL AND description != '' "
            "ORDER BY autoplius_id"
        ).fetchall()

    if args.repair_errors:
        rows = [row for row in rows if is_translation_error(row["description_ru"])]
    elif not args.force:
        rows = [row for row in rows if not row["description_ru"]]

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    translated = skipped = failed = 0
    for idx, row in enumerate(rows, start=1):
        listing_id = int(row["autoplius_id"])
        original = row["description"] or ""
        result = translate_to_russian(
            original,
            enabled=settings.translate_descriptions,
            min_delay_sec=settings.translate_delay_sec,
        )
        if not result:
            failed += 1
            if args.repair_errors:
                with connect(settings.db_path) as conn:
                    conn.execute(
                        "UPDATE listings SET description_ru = NULL, updated_at = ? WHERE autoplius_id = ?",
                        (_utc_now(), listing_id),
                    )
            logger.info("[%s/%s] #%s translate failed", idx, len(rows), listing_id)
            continue
        if not args.force and not args.repair_errors and result == original and row["description_ru"]:
            skipped += 1
            continue

        with connect(settings.db_path) as conn:
            conn.execute(
                "UPDATE listings SET description_ru = ?, updated_at = ? WHERE autoplius_id = ?",
                (result, _utc_now(), listing_id),
            )
        translated += 1
        logger.info("[%s/%s] #%s translated (%s chars)", idx, len(rows), listing_id, len(result))

    logger.info(
        "backfill-summary: translated=%s skipped=%s failed=%s total=%s force=%s",
        translated,
        skipped,
        failed,
        len(rows),
        args.force,
    )


if __name__ == "__main__":
    main()
