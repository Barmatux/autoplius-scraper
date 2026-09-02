"""SQL aggregations for index filter dropdowns (no full listing scan)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoplius.spec_filters import (
    TRANSMISSION_FILTER_GROUPS,
    format_volume_option,
    multi_filter_selection_label,
    transmission_filter_checked_slugs,
    transmission_filter_display_label,
)
from autoplius.title_sql import title_make_expr, title_model_expr
from scraper.db import connect
from scraper.listing_sql_filters import (
    BLOCKED_MAKES,
    ListingFilters,
    _reg_year_expr,
    build_listing_where,
)
from scraper.query_cache import cached_listing_filter_options


def _where_sql(filters: ListingFilters) -> tuple[str, list[Any]]:
    clauses, params = build_listing_where(filters)
    if not clauses:
        return "", params
    return f"WHERE {' AND '.join(clauses)}", params


@dataclass
class ListingFilterOptions:
    city_options: list[dict[str, Any]]
    make_model_options: dict[str, Any]
    year_options: list[int]
    body_type_options: list[str]
    fuel_options: list[str]
    transmission_values: list[str]
    volume_options: list[str]

    def spec_filters(
        self,
        *,
        selected_body_types: list[str],
        selected_fuels: list[str],
        selected_transmissions: list[str],
    ) -> dict[str, Any]:
        return {
            "body_type_options": self.body_type_options,
            "fuel_options": self.fuel_options,
            "transmission_groups": TRANSMISSION_FILTER_GROUPS,
            "transmission_checked": transmission_filter_checked_slugs(selected_transmissions),
            "volume_options": self.volume_options,
            "body_type_display": multi_filter_selection_label(selected_body_types, "Любой"),
            "fuel_display": multi_filter_selection_label(selected_fuels, "Любое"),
            "transmission_display": transmission_filter_display_label(selected_transmissions),
        }


def fetch_listing_filter_options(
    db_path: Path,
    filters: ListingFilters,
) -> ListingFilterOptions:
    return cached_listing_filter_options(
        db_path,
        filters,
        _load_listing_filter_options,
    )


def _load_listing_filter_options(
    db_path: Path,
    filters: ListingFilters,
) -> ListingFilterOptions:
    if not db_path.is_file():
        return ListingFilterOptions([], {"makes": [], "modelMap": {}, "makeCounts": {}}, [], [], [], [], [])

    where, params = _where_sql(filters)
    make_expr = title_make_expr()
    model_expr = title_model_expr()
    year_expr = _reg_year_expr()
    blocked_checks = " AND ".join(f"lower({make_expr}) NOT LIKE ?" for _ in BLOCKED_MAKES)
    blocked_params = [f"{make.casefold()}%" for make in BLOCKED_MAKES]

    with connect(db_path) as conn:
        city_rows = conn.execute(
            f"""
            SELECT trim(COALESCE(city, '')) AS name, COUNT(*) AS count
            FROM listings
            {where}
              {"AND" if where else "WHERE"} trim(COALESCE(city, '')) != ''
            GROUP BY trim(COALESCE(city, ''))
            ORDER BY count DESC, name COLLATE NOCASE
            """,
            params,
        ).fetchall()

        make_rows = conn.execute(
            f"""
            SELECT {make_expr} AS make, {model_expr} AS model, COUNT(*) AS count
            FROM listings
            {where}
              {"AND" if where else "WHERE"} {make_expr} != ''
              AND {make_expr} != '—'
              AND ({blocked_checks})
            GROUP BY make, model
            ORDER BY make COLLATE NOCASE, model COLLATE NOCASE
            """,
            [*params, *blocked_params],
        ).fetchall()

        year_rows = conn.execute(
            f"""
            SELECT DISTINCT {year_expr} AS year_value
            FROM listings
            {where}
              {"AND" if where else "WHERE"} {year_expr} IS NOT NULL
              AND {year_expr} > 1900
            ORDER BY year_value DESC
            """,
            params,
        ).fetchall()

        body_rows = conn.execute(
            f"""
            SELECT trim(COALESCE(body_type, '')) AS value
            FROM listings
            {where}
              {"AND" if where else "WHERE"} trim(COALESCE(body_type, '')) != ''
            GROUP BY trim(COALESCE(body_type, ''))
            ORDER BY value COLLATE NOCASE
            """,
            params,
        ).fetchall()

        fuel_rows = conn.execute(
            f"""
            SELECT trim(COALESCE(fuel, '')) AS value
            FROM listings
            {where}
              {"AND" if where else "WHERE"} trim(COALESCE(fuel, '')) != ''
            GROUP BY trim(COALESCE(fuel, ''))
            ORDER BY value COLLATE NOCASE
            """,
            params,
        ).fetchall()

        transmission_rows = conn.execute(
            f"""
            SELECT trim(COALESCE(transmission, '')) AS value
            FROM listings
            {where}
              {"AND" if where else "WHERE"} trim(COALESCE(transmission, '')) != ''
            GROUP BY trim(COALESCE(transmission, ''))
            ORDER BY value COLLATE NOCASE
            """,
            params,
        ).fetchall()

        volume_rows = conn.execute(
            f"""
            SELECT DISTINCT ROUND(engine_liters, 1) AS liters
            FROM listings
            {where}
              {"AND" if where else "WHERE"} engine_liters IS NOT NULL
            ORDER BY liters
            """,
            params,
        ).fetchall()

    model_map: dict[str, set[str]] = {}
    make_counts: dict[str, int] = {}
    for row in make_rows:
        make = (row["make"] or "").strip()
        model = (row["model"] or "").strip()
        count = int(row["count"] or 0)
        if not make or make == "—":
            continue
        make_counts[make] = make_counts.get(make, 0) + count
        if model:
            model_map.setdefault(make, set()).add(model)

    makes = sorted(make_counts.keys(), key=str.casefold)
    return ListingFilterOptions(
        city_options=[
            {"name": row["name"], "count": int(row["count"])}
            for row in city_rows
        ],
        make_model_options={
            "makes": makes,
            "modelMap": {
                make: sorted(models, key=str.casefold)
                for make, models in sorted(model_map.items(), key=lambda pair: pair[0].casefold())
            },
            "makeCounts": make_counts,
        },
        year_options=[int(row["year_value"]) for row in year_rows],
        body_type_options=[row["value"] for row in body_rows],
        fuel_options=[row["value"] for row in fuel_rows],
        transmission_values=[row["value"] for row in transmission_rows],
        volume_options=[format_volume_option(float(row["liters"])) for row in volume_rows],
    )
