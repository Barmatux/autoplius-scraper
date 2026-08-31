#!/usr/bin/env python3
"""Rewrite stored listing fields to Russian using localize dictionaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.localize import localize_listing
from autoplius.urls import configure_base_url, normalize_listing_url
from scraper.db import connect, init_db, row_to_listing


def backfill(db_path: Path, *, base_url: str | None = None) -> int:
    if base_url:
        configure_base_url(base_url)
    init_db(db_path)
    updated = 0
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM listings").fetchall()
        for row in rows:
            listing = row_to_listing(row)
            # row_to_listing already localizes; normalize URL separately.
            listing["url"] = normalize_listing_url(listing.get("url") or "")
            conn.execute(
                """
                UPDATE listings SET
                    url = ?,
                    title = ?,
                    body_type = ?,
                    fuel = ?,
                    transmission = ?,
                    engine = ?,
                    city = ?,
                    parameters_json = ?
                WHERE autoplius_id = ?
                """,
                (
                    listing["url"],
                    listing["title"],
                    listing["body_type"],
                    listing["fuel"],
                    listing["transmission"],
                    listing["engine"],
                    listing["city"],
                    json.dumps(listing.get("parameters") or {}, ensure_ascii=False),
                    listing["autoplius_id"],
                ),
            )
            updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Path to app.db")
    parser.add_argument(
        "--base-url",
        default="https://ru.autoplius.lt",
        help="Base URL for listing link normalization",
    )
    args = parser.parse_args()
    count = backfill(args.db, base_url=args.base_url)
    print(f"Localized {count} listings in {args.db}")


if __name__ == "__main__":
    main()
