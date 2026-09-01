"""Characteristic filters: body type, fuel, transmission, engine volume."""

from __future__ import annotations

from typing import Any

from autoplius.engine_volume import engine_volume_liters
from autoplius.transmission_labels import (
    TRANSMISSION_FILTER_GROUPS,
    multi_filter_selection_label,
    parse_transmission_filter_values,
    transmission_db_values_for_slugs,
    transmission_filter_checked_slugs,
    transmission_filter_display_label,
)


def parse_multi_param_values(raw_values: list[str] | None) -> list[str]:
    if not raw_values:
        return []
    seen: set[str] = set()
    values: list[str] = []
    for raw in raw_values:
        value = (raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def parse_volume_param(raw: str | None) -> float | None:
    text = (raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0 or value > 20:
        return None
    return round(value, 1)


def format_volume_option(liters: float) -> str:
    if abs(liters - round(liters)) < 0.05:
        return str(int(round(liters)))
    return f"{liters:.1f}"


def _distinct_field_values(listings: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in listings:
        value = (item.get(field) or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return sorted(values, key=str.casefold)


def build_body_type_options(listings: list[dict[str, Any]]) -> list[str]:
    return _distinct_field_values(listings, "body_type")


def build_fuel_options(listings: list[dict[str, Any]]) -> list[str]:
    return _distinct_field_values(listings, "fuel")


def build_transmission_raw_values(listings: list[dict[str, Any]]) -> list[str]:
    return _distinct_field_values(listings, "transmission")


def build_volume_options(listings: list[dict[str, Any]]) -> list[str]:
    seen: set[float] = set()
    values: list[float] = []
    for item in listings:
        liters = engine_volume_liters(item)
        if liters is None:
            continue
        rounded = round(liters, 1)
        if rounded in seen:
            continue
        seen.add(rounded)
        values.append(rounded)
    values.sort()
    return [format_volume_option(value) for value in values]


def filter_by_body_types(
    listings: list[dict[str, Any]],
    selected: list[str],
) -> list[dict[str, Any]]:
    if not selected:
        return listings
    allowed = set(selected)
    return [
        item
        for item in listings
        if (item.get("body_type") or "").strip() in allowed
    ]


def filter_by_fuel_types(
    listings: list[dict[str, Any]],
    selected: list[str],
) -> list[dict[str, Any]]:
    if not selected:
        return listings
    allowed = set(selected)
    return [
        item
        for item in listings
        if (item.get("fuel") or "").strip() in allowed
    ]


def filter_by_transmissions(
    listings: list[dict[str, Any]],
    slugs: list[str],
    raw_values: list[str],
) -> list[dict[str, Any]]:
    if not slugs:
        return listings
    match_values = set(transmission_db_values_for_slugs(raw_values, slugs))
    if not match_values:
        return []
    return [
        item
        for item in listings
        if (item.get("transmission") or "").strip() in match_values
    ]


def filter_by_volume_range(
    listings: list[dict[str, Any]],
    volume_from: float | None,
    volume_to: float | None,
) -> list[dict[str, Any]]:
    if volume_from is None and volume_to is None:
        return listings
    if volume_from is not None and volume_to is not None and volume_from > volume_to:
        volume_from, volume_to = volume_to, volume_from
    result: list[dict[str, Any]] = []
    for item in listings:
        liters = engine_volume_liters(item)
        if liters is None:
            continue
        if volume_from is not None and liters + 0.001 < volume_from:
            continue
        if volume_to is not None and liters - 0.001 > volume_to:
            continue
        result.append(item)
    return result


def build_spec_filter_options(
    listings: list[dict[str, Any]],
    *,
    selected_body_types: list[str],
    selected_fuels: list[str],
    selected_transmissions: list[str],
) -> dict[str, Any]:
    return {
        "body_type_options": build_body_type_options(listings),
        "fuel_options": build_fuel_options(listings),
        "transmission_groups": TRANSMISSION_FILTER_GROUPS,
        "transmission_checked": transmission_filter_checked_slugs(selected_transmissions),
        "volume_options": build_volume_options(listings),
        "body_type_display": multi_filter_selection_label(selected_body_types, "Любой"),
        "fuel_display": multi_filter_selection_label(selected_fuels, "Любое"),
        "transmission_display": transmission_filter_display_label(selected_transmissions),
    }
