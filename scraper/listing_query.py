"""SQL-backed listing queries for the index page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoplius.engine_volume import engine_volume_liters
from scraper.db import (
    LISTING_COLUMNS_FILTER,
    _listing_sort_sql,
    connect,
    row_to_listing,
)
from scraper.listing_sql_filters import ListingFilters, build_listing_where


def _volume_item_from_row(row: Any) -> dict[str, Any]:
    return {
        "title": row["title"],
        "engine": row["engine"],
        "description": row["description"],
        "description_ru": row["description_ru"],
        "parameters": json.loads(row["parameters_json"] or "{}"),
    }


def count_listings(db_path: Path, filters: ListingFilters) -> int:
    if not db_path.is_file():
        return 0
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COUNT(*) FROM listings {where}"
    with connect(db_path) as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def fetch_listing_ids(
    db_path: Path,
    filters: ListingFilters,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[int]:
    if not db_path.is_file():
        return []
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT autoplius_id FROM listings {where} "
        f"ORDER BY {_listing_sort_sql(filters.sort)}"
    )
    query_params = list(params)
    if limit is not None:
        sql += " LIMIT ?"
        query_params.append(int(limit))
        if offset is not None:
            sql += " OFFSET ?"
            query_params.append(int(offset))
    with connect(db_path) as conn:
        rows = conn.execute(sql, query_params).fetchall()
    return [int(row[0]) for row in rows]


def fetch_listings_for_options(
    db_path: Path,
    filters: ListingFilters,
) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT {LISTING_COLUMNS_FILTER} FROM listings {where}"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_listing(row) for row in rows]


def backfill_engine_liters(db_path: Path, *, batch_size: int = 500) -> int:
    if not db_path.is_file():
        return 0
    updated = 0
    with connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
        if "engine_liters" not in cols:
            return 0
        last_id = 0
        while True:
            rows = conn.execute(
                """
                SELECT autoplius_id, title, engine, parameters_json, description, description_ru
                FROM listings
                WHERE engine_liters IS NULL AND autoplius_id > ?
                ORDER BY autoplius_id
                LIMIT ?
                """,
                (last_id, batch_size),
            ).fetchall()
            if not rows:
                break
            for row in rows:
                liters = engine_volume_liters(_volume_item_from_row(row))
                conn.execute(
                    "UPDATE listings SET engine_liters = ? WHERE autoplius_id = ?",
                    (liters, row["autoplius_id"]),
                )
                updated += 1
            last_id = int(rows[-1]["autoplius_id"])
    return updated
