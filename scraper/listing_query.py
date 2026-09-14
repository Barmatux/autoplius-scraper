"""SQL-backed listing queries for the index page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoplius.engine_volume import engine_volume_liters
from autoplius.labels import mileage_from_parameters, parse_mileage_km
from scraper.db import (
    _listing_sort_sql,
    _row_scalar,
    connect,
    row_to_listing,
)
from scraper.db_backend import db_ready, using_postgres
from scraper.listing_sql_filters import ListingFilters, build_listing_where
from scraper.sql_dialect import (
    listing_id_expr,
    listing_pk_where,
    listing_select_columns,
    listings_source_clause,
    parameters_col,
)


def _volume_item_from_row(row: Any) -> dict[str, Any]:
    raw = row["parameters_json"] if "parameters_json" in row.keys() else row.get("parameters")
    if isinstance(raw, dict):
        parameters = raw
    else:
        try:
            parameters = json.loads(raw or "{}")
        except (TypeError, json.JSONDecodeError):
            parameters = {}
    return {
        "title": row["title"],
        "engine": row["engine"],
        "description": row["description"],
        "description_ru": row["description_ru"],
        "parameters": parameters if isinstance(parameters, dict) else {},
    }


def _parameters_from_row(row: Any) -> dict[str, Any]:
    raw = None
    keys = row.keys() if hasattr(row, "keys") else ()
    if "parameters_json" in keys:
        raw = row["parameters_json"]
    elif isinstance(row, dict) and "parameters" in row:
        raw = row["parameters"]
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError, KeyError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def count_listings(db_path: Path, filters: ListingFilters) -> int:
    if not db_ready(db_path):
        return 0
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COUNT(*) AS c FROM listings {where}"
    with connect(db_path) as conn:
        return int(_row_scalar(conn.execute(sql, params).fetchone()) or 0)


def fetch_listing_ids(
    db_path: Path,
    filters: ListingFilters,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[int]:
    if not db_ready(db_path):
        return []
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    id_expr = listing_id_expr()
    sql = (
        f"SELECT {id_expr} AS autoplius_id FROM listings {where} "
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
    return [int(row["autoplius_id"]) for row in rows]


def fetch_listings_for_options(
    db_path: Path,
    filters: ListingFilters,
) -> list[dict[str, Any]]:
    if not db_ready(db_path):
        return []
    clauses, params = build_listing_where(filters)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = listing_select_columns("filter")
    sql = f"SELECT {columns} FROM listings {where}"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_listing(row) for row in rows]


def backfill_engine_liters(db_path: Path, *, batch_size: int = 500, force: bool = False) -> int:
    if using_postgres():
        # Listing maintenance is owned by scrape-platform after cutover.
        return 0
    if not db_ready(db_path):
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
    if using_postgres():
        return 0
    if not db_ready(db_path):
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
