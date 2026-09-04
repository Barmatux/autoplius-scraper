"""SQL-backed listing queries for the index page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoplius.engine_volume import engine_volume_liters
from autoplius.labels import mileage_from_parameters, parse_mileage_km
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


def _parameters_from_row(row: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(row["parameters_json"] or "{}")
    except (TypeError, json.JSONDecodeError, KeyError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


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


def backfill_engine_liters(db_path: Path, *, batch_size: int = 500, force: bool = False) -> int:
    if not db_path.is_file():
        return 0
    updated = 0
    with connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
        if "engine_liters" not in cols:
            return 0
        last_id = 0
        null_clause = "" if force else "engine_liters IS NULL AND "
        while True:
            rows = conn.execute(
                f"""
                SELECT autoplius_id, title, engine, parameters_json, description, description_ru, engine_liters
                FROM listings
                WHERE {null_clause} autoplius_id > ?
                ORDER BY autoplius_id
                LIMIT ?
                """,
                (last_id, batch_size),
            ).fetchall()
            if not rows:
                break
            for row in rows:
                item = _volume_item_from_row(row)
                item["engine_liters"] = None
                liters = engine_volume_liters(item)
                if liters is None:
                    if not force:
                        continue
                    if row["engine_liters"] is None:
                        continue
                elif not force and liters == row["engine_liters"]:
                    continue
                elif force and liters == row["engine_liters"]:
                    continue
                conn.execute(
                    "UPDATE listings SET engine_liters = ? WHERE autoplius_id = ?",
                    (liters, row["autoplius_id"]),
                )
                updated += 1
            last_id = int(rows[-1]["autoplius_id"])
    return updated


def backfill_mileage_km(db_path: Path, *, batch_size: int = 500, force: bool = False) -> int:
    """Fill mileage_km from parameters_json when the column is empty."""
    if not db_path.is_file():
        return 0
    updated = 0
    with connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
        if "mileage_km" not in cols or "parameters_json" not in cols:
            return 0
        last_id = 0
        null_clause = "" if force else "mileage_km IS NULL AND "
        while True:
            rows = conn.execute(
                f"""
                SELECT autoplius_id, mileage_km, parameters_json
                FROM listings
                WHERE {null_clause} autoplius_id > ?
                ORDER BY autoplius_id
                LIMIT ?
                """,
                (last_id, batch_size),
            ).fetchall()
            if not rows:
                break
            for row in rows:
                parsed = mileage_from_parameters(_parameters_from_row(row))
                if parsed is None:
                    continue
                current = parse_mileage_km(row["mileage_km"])
                if not force and current is not None:
                    continue
                if current == parsed:
                    continue
                conn.execute(
                    "UPDATE listings SET mileage_km = ? WHERE autoplius_id = ?",
                    (parsed, row["autoplius_id"]),
                )
                updated += 1
            last_id = int(rows[-1]["autoplius_id"])
    return updated
