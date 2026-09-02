"""Build SQLite WHERE clauses for listing index filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autoplius.make_model_filters import BLOCKED_MAKES
from autoplius.title_sql import title_make_expr

MIN_CATALOG_YEAR = 2008
PICKUP_BODY_MARKERS = ("%pikap%", "%pickup%", "%пикап%")


def _reg_year_expr() -> str:
    return "CAST(substr(COALESCE(year, ''), 1, 4) AS INTEGER)"


def _reg_month_expr() -> str:
    return "CAST(COALESCE(NULLIF(substr(COALESCE(year, ''), 6, 2), ''), '01') AS INTEGER)"


def _age_months_expr() -> str:
    year_expr = _reg_year_expr()
    month_expr = _reg_month_expr()
    return (
        f"(({year_expr} IS NOT NULL AND {year_expr} > 1900) * "
        f"((CAST(strftime('%Y', 'now') AS INTEGER) - {year_expr}) * 12 + "
        f"(CAST(strftime('%m', 'now') AS INTEGER) - {month_expr})))"
    )


def _title_make_expr() -> str:
    return f"lower({title_make_expr()})"


def _pickup_clause() -> str:
    pickup_checks = " AND ".join(
        f"lower(COALESCE(body_type, '')) NOT LIKE '{marker}'" for marker in PICKUP_BODY_MARKERS
    )
    return f"({pickup_checks})"


@dataclass
class ListingFilters:
    q: str = ""
    min_price: int | None = None
    max_price: int | None = None
    sort: str = "added_desc"
    details_only: bool = False
    listing_status: str = "active"
    catalog_filter: bool = True
    exclude_blocked_makes: bool = True
    older_than_3_only: bool = False
    passable_only: bool = False
    engine_upto_liters: float | None = None
    engine_volume_missing: bool = False
    volume_from: float | None = None
    volume_to: float | None = None
    cities: list[str] = field(default_factory=list)
    body_types: list[str] = field(default_factory=list)
    fuels: list[str] = field(default_factory=list)
    transmissions: list[str] = field(default_factory=list)
    vehicle_rows: list[dict[str, str]] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None


def build_listing_where(filters: ListingFilters) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if filters.details_only:
        clauses.append("detail_scraped = 1")
    if filters.listing_status == "active":
        clauses.append("(status IS NULL OR status = 'active')")
    elif filters.listing_status == "archived":
        clauses.append("status = 'archived'")
    elif filters.listing_status != "all":
        clauses.append("(status IS NULL OR status = 'active')")

    if filters.min_price is not None:
        clauses.append("price_eur IS NOT NULL AND price_eur >= ?")
        params.append(filters.min_price)
    if filters.max_price is not None:
        clauses.append("price_eur IS NOT NULL AND price_eur <= ?")
        params.append(filters.max_price)

    if filters.q.strip():
        like = f"%{filters.q.strip().lower()}%"
        clauses.append(
            """(
                lower(COALESCE(title,'')) LIKE ?
                OR lower(COALESCE(city,'')) LIKE ?
                OR lower(COALESCE(fuel,'')) LIKE ?
                OR lower(COALESCE(phone,'')) LIKE ?
                OR lower(COALESCE(vin_masked,'')) LIKE ?
                OR lower(COALESCE(description,'')) LIKE ?
                OR lower(COALESCE(description_ru,'')) LIKE ?
                OR lower(COALESCE(parameters_json,'')) LIKE ?
                OR CAST(autoplius_id AS TEXT) LIKE ?
            )"""
        )
        params.extend([like] * 9)

    if filters.exclude_blocked_makes:
        clauses.append(_pickup_clause())
        blocked_checks = " AND ".join(
            f"{_title_make_expr()} NOT LIKE ?" for _ in BLOCKED_MAKES
        )
        clauses.append(f"({blocked_checks})")
        params.extend(f"{make.casefold()}%" for make in BLOCKED_MAKES)

    if filters.catalog_filter:
        year_expr = _reg_year_expr()
        clauses.append(f"({year_expr} IS NULL OR {year_expr} >= ?)")
        params.append(MIN_CATALOG_YEAR)

    age_months = _age_months_expr()
    if filters.older_than_3_only:
        clauses.append(f"({age_months} > ?)")
        params.append(36)
    if filters.passable_only:
        clauses.append(f"({age_months} >= ? AND {age_months} < ?)")
        params.extend([36, 72])

    if filters.engine_volume_missing:
        clauses.append("engine_liters IS NULL")
        year_expr = _reg_year_expr()
        clauses.append(f"({year_expr} IS NULL OR {year_expr} >= ?)")
        params.append(MIN_CATALOG_YEAR)
    elif filters.engine_upto_liters is not None:
        clauses.append("engine_liters IS NOT NULL AND engine_liters <= ?")
        params.append(filters.engine_upto_liters)

    volume_from = filters.volume_from
    volume_to = filters.volume_to
    if volume_from is not None and volume_to is not None and volume_from > volume_to:
        volume_from, volume_to = volume_to, volume_from
    if volume_from is not None:
        clauses.append("engine_liters IS NOT NULL AND engine_liters >= ?")
        params.append(volume_from)
    if volume_to is not None:
        clauses.append("engine_liters IS NOT NULL AND engine_liters <= ?")
        params.append(volume_to)

    if filters.cities:
        placeholders = ",".join("?" for _ in filters.cities)
        clauses.append(f"trim(COALESCE(city, '')) IN ({placeholders})")
        params.extend(filters.cities)

    if filters.body_types:
        placeholders = ",".join("?" for _ in filters.body_types)
        clauses.append(f"trim(COALESCE(body_type, '')) IN ({placeholders})")
        params.extend(filters.body_types)

    if filters.fuels:
        placeholders = ",".join("?" for _ in filters.fuels)
        clauses.append(f"trim(COALESCE(fuel, '')) IN ({placeholders})")
        params.extend(filters.fuels)

    if filters.transmissions:
        placeholders = ",".join("?" for _ in filters.transmissions)
        clauses.append(f"trim(COALESCE(transmission, '')) IN ({placeholders})")
        params.extend(filters.transmissions)

    active_rows = [
        row
        for row in filters.vehicle_rows
        if (row.get("make") or "").strip() or (row.get("model") or "").strip()
    ]
    if active_rows:
        row_clauses: list[str] = []
        for row in active_rows:
            make = (row.get("make") or "").strip()
            model = (row.get("model") or "").strip()
            if make and model:
                space_pat = f"{make.casefold()} {model.casefold()}%"
                comma_pat = f"{make.casefold()},%{model.casefold()}%"
                row_clauses.append(
                    "(lower(COALESCE(title, '')) LIKE ? OR lower(COALESCE(title, '')) LIKE ?)"
                )
                params.extend([space_pat, comma_pat])
            elif make:
                space_pat = f"{make.casefold()} %"
                comma_pat = f"{make.casefold()},%"
                row_clauses.append(
                    "(lower(COALESCE(title, '')) LIKE ? OR lower(COALESCE(title, '')) LIKE ?)"
                )
                params.extend([space_pat, comma_pat])
            elif model:
                row_clauses.append("lower(COALESCE(title, '')) LIKE ?")
                params.append(f"% {model.casefold()}%")
        if row_clauses:
            clauses.append("(" + " OR ".join(row_clauses) + ")")

    year_expr = _reg_year_expr()
    if filters.year_from is not None:
        clauses.append(f"{year_expr} >= ?")
        params.append(filters.year_from)
    if filters.year_to is not None:
        clauses.append(f"{year_expr} <= ?")
        params.append(filters.year_to)

    return clauses, params
