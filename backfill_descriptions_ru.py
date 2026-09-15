#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.listing_description import needs_description_translation
from autoplius.translate import is_translation_error, translate_to_russian
from scraper.config import Settings
from scraper.db import connect, init_db, update_listing_description_ru
from scraper.sql_dialect import listing_id_expr, listings_source_clause

logger = logging.getLogger(__name__)


def _parse_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def _and_source(clauses: list[str]) -> None:
    source = listings_source_clause()
    if source:
        clauses.append(source)


def _fetch_candidates(
    db_path: Path,
    *,
    id_filter: list[int],
    force: bool,
    repair_errors: bool,
    active_only: bool,
    limit: int,
) -> list:
    id_expr = listing_id_expr()
    with connect(db_path) as conn:
        if id_filter:
            placeholders = ",".join("?" for _ in id_filter)
            clauses = [
                f"{id_expr} IN ({placeholders})",
                "description IS NOT NULL",
                "trim(description) != ''",
            ]
            _and_source(clauses)
            rows = conn.execute(
                f"""
                SELECT {id_expr} AS autoplius_id, description, description_ru
                FROM listings
                WHERE {' AND '.join(clauses)}
                ORDER BY {id_expr}
                """,
                id_filter,
            ).fetchall()
        else:
            clauses = [
                "description IS NOT NULL",
                "trim(description) != ''",
            ]
            _and_source(clauses)
            if active_only:
                clauses.append("(status IS NULL OR status = 'active')")
            if not repair_errors and not force:
                clauses.append(
                    "("
                    "description_ru IS NULL OR trim(description_ru) = '' "
                    "OR description_ru = description"
                    ")"
                )
            sql = (
                f"SELECT {id_expr} AS autoplius_id, description, description_ru "
                "FROM listings "
                f"WHERE {' AND '.join(clauses)} "
                "ORDER BY COALESCE(updated_at, last_seen_at, first_seen_at) DESC, "
                f"{id_expr} DESC"
            )
            fetch_limit = max(limit * 4, 200) if limit > 0 else None
            params: list = []
            if fetch_limit:
                sql += " LIMIT ?"
                params.append(int(fetch_limit))
            rows = conn.execute(sql, params).fetchall()

    if id_filter:
        if not force:
            rows = [
                row
                for row in rows
                if needs_description_translation(
                    {
                        "description": row["description"],
                        "description_ru": row["description_ru"],
                    }
                )
            ]
        return rows

    filtered = []
    for row in rows:
        item = {
            "description": row["description"],
            "description_ru": row["description_ru"],
        }
        if repair_errors:
            if is_translation_error(row["description_ru"]):
                filtered.append(row)
            continue
        if force:
            if needs_description_translation(
                {"description": row["description"], "description_ru": None}
            ):
                filtered.append(row)
            continue
        if needs_description_translation(item):
            filtered.append(row)

    if limit and limit > 0:
        filtered = filtered[:limit]
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Russian descriptions for existing listings")
    parser.add_argument("--limit", type=int, default=0, help="Limit listings (0 = all missing)")
    parser.add_argument("--force", action="store_true", help="Re-translate even if description_ru exists")
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated listing IDs to translate (skips missing-only filter)",
    )
    parser.add_argument(
        "--repair-errors",
        action="store_true",
        help="Re-translate rows where description_ru contains translator error text",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        default=True,
        help="Only active listings (default: true)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also process archived listings",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    init_db(settings.db_path)

    id_filter = _parse_ids(args.ids)
    active_only = not args.include_archived

    rows = _fetch_candidates(
        settings.db_path,
        id_filter=id_filter,
        force=args.force,
        repair_errors=args.repair_errors,
        active_only=active_only and not id_filter,
        limit=args.limit,
    )

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
                update_listing_description_ru(settings.db_path, listing_id, None)
            logger.info("[%s/%s] #%s translate failed", idx, len(rows), listing_id)
            continue
        if not args.force and not args.repair_errors and result == original and row["description_ru"]:
            skipped += 1
            continue

        update_listing_description_ru(settings.db_path, listing_id, result)
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
