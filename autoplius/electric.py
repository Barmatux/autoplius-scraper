"""Detect pure-electric (non-hybrid) Autoplius listings."""

from __future__ import annotations

from typing import Any

ELECTRIC_MARKERS = (
    "электр",
    "elektr",
    "elektra",
    "electric",
)
HYBRID_OR_ICE_MARKERS = (
    "/",
    "гибрид",
    "hybrid",
    "plug-in",
    "plugin",
    "бенз",
    "benzin",
    "byenzin",
    "дизел",
    "dizel",
    "dyzel",
    "diesel",
    "petrol",
    "gasoline",
    "газ",
)


def is_pure_electric_fuel(fuel: str | None) -> bool:
    """True for battery-only cars; false for hybrids and ICE."""
    text = (fuel or "").casefold().strip()
    if not text:
        return False
    if not any(marker in text for marker in ELECTRIC_MARKERS):
        return False
    if any(marker in text for marker in HYBRID_OR_ICE_MARKERS):
        return False
    return True


def is_pure_electric_listing(item: dict[str, Any]) -> bool:
    if int(item.get("manual_electric") or 0):
        return True
    return is_pure_electric_fuel(item.get("fuel"))


def electric_sql_clause(*, include: bool) -> str:
    """SQLite expression: listing is (or is not) treated as pure electric.

    Note: SQLite lower() is ASCII-only, so Cyrillic markers are matched with
    literal substrings instead of lower(fuel). Latin markers avoid bare
    'elektr%' so city names like Elektrėnai are not treated as EVs.
    """
    auto = """(
        (
          COALESCE(fuel, '') LIKE '%лектр%'
          OR COALESCE(fuel, '') LIKE '%Лектр%'
          OR lower(COALESCE(fuel, '')) LIKE 'elektra%'
          OR lower(COALESCE(fuel, '')) LIKE 'electric%'
          OR lower(COALESCE(fuel, '')) LIKE 'electricity%'
        )
        AND COALESCE(fuel, '') NOT LIKE '%/%'
        AND COALESCE(fuel, '') NOT LIKE '%гибрид%'
        AND COALESCE(fuel, '') NOT LIKE '%Гибрид%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%hybrid%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%plug-in%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%plugin%'
        AND COALESCE(fuel, '') NOT LIKE '%бенз%'
        AND COALESCE(fuel, '') NOT LIKE '%Бенз%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%benzin%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%byenzin%'
        AND COALESCE(fuel, '') NOT LIKE '%дизел%'
        AND COALESCE(fuel, '') NOT LIKE '%Дизел%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%dizel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%dyzel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%diesel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%petrol%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%gasoline%'
    )"""
    expr = f"(COALESCE(manual_electric, 0) = 1 OR {auto})"
    return expr if include else f"NOT {expr}"
