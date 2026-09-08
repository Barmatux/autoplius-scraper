"""Top makes for the cars nav flyout (Автомобили из Литвы)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from autoplius.make_model_filters import BLOCKED_MAKES
from autoplius.title_sql import title_make_expr
from scraper.db import connect
from scraper.listing_sql_filters import ListingFilters, build_listing_where

FALLBACK_POPULAR_MAKES: tuple[str, ...] = (
    "Volkswagen",
    "BMW",
    "Audi",
    "Mercedes-Benz",
    "Toyota",
    "Ford",
    "Opel",
    "Peugeot",
    "Volvo",
    "Nissan",
    "Hyundai",
)

POPULAR_MAKE_LIMIT = 11
_CACHE_TTL_SEC = 180.0
_cache: dict[str, tuple[float, list[str]]] = {}


def _db_token(db_path: Path) -> str:
    try:
        stat = db_path.resolve().stat()
    except OSError:
        return str(db_path)
    return f"{db_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def _load_top_makes(db_path: Path) -> list[str]:
    if not db_path.is_file():
        return list(FALLBACK_POPULAR_MAKES[:POPULAR_MAKE_LIMIT])

    filters = ListingFilters(exclude_electric=True, catalog_filter=True)
    where_clauses, params = build_listing_where(filters)
    make_expr = title_make_expr()
    blocked_checks = " AND ".join(f"lower({make_expr}) NOT LIKE ?" for _ in BLOCKED_MAKES)
    blocked_params = [f"{make.casefold()}%" for make in BLOCKED_MAKES]
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    prefix = "AND" if where_sql else "WHERE"

    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {make_expr} AS make, COUNT(*) AS count
            FROM listings
            {where_sql}
              {prefix} {make_expr} != ''
              AND {make_expr} != '—'
              AND ({blocked_checks})
            GROUP BY make
            ORDER BY count DESC, make COLLATE NOCASE
            LIMIT ?
            """,
            [*params, *blocked_params, POPULAR_MAKE_LIMIT],
        ).fetchall()

    makes = [(row["make"] or "").strip() for row in rows if (row["make"] or "").strip()]
    if len(makes) >= POPULAR_MAKE_LIMIT:
        return makes[:POPULAR_MAKE_LIMIT]
    for fallback in FALLBACK_POPULAR_MAKES:
        if fallback not in makes:
            makes.append(fallback)
        if len(makes) >= POPULAR_MAKE_LIMIT:
            break
    return makes[:POPULAR_MAKE_LIMIT]


def top_makes_for_nav(db_path: Path) -> list[str]:
    key = _db_token(db_path)
    entry = _cache.get(key)
    now = time.monotonic()
    if entry is not None and entry[0] > now:
        return list(entry[1])
    makes = _load_top_makes(db_path)
    _cache[key] = (now + _CACHE_TTL_SEC, list(makes))
    return makes


def make_nav_links(
    *,
    index_path: str = "/",
    sort: str = "added_desc",
    makes: list[str] | None = None,
) -> list[dict[str, Any]]:
    base = index_path.rstrip("/") or "/"
    all_href = f"{base}?{urlencode({'tab': 'all', 'sort': sort, 'page': '1'})}"
    links: list[dict[str, Any]] = [{"label": "Все", "href": all_href}]
    for make in makes or list(FALLBACK_POPULAR_MAKES[:POPULAR_MAKE_LIMIT]):
        href = f"{base}?{urlencode({'tab': 'all', 'sort': sort, 'page': '1', 'make': make})}"
        links.append({"label": make, "href": href})
    return links
