from __future__ import annotations

from collections import Counter
from typing import Any

from autoplius.catalog_filters import listing_year
from autoplius.listing_display import listing_make_model

BLOCKED_MAKES = frozenset({"Ligier"})


def is_blocked_make(make: str | None) -> bool:
    text = (make or "").strip()
    if not text or text == "—":
        return False
    folded = text.casefold()
    return any(blocked.casefold() == folded for blocked in BLOCKED_MAKES)


def exclude_blocked_makes(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in listings
        if not is_blocked_make(listing_make_model(item)[0])
    ]


def parse_optional_year(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        year = int(raw)
    except ValueError:
        return None
    if year < 1950 or year > 2100:
        return None
    return year


def parse_vehicle_filter_rows(
    makes: list[str],
    models: list[str],
) -> list[dict[str, str]]:
    if not makes and not models:
        return [{"make": "", "model": ""}]
    count = max(len(makes), len(models))
    rows: list[dict[str, str]] = []
    for index in range(count):
        make = (makes[index] if index < len(makes) else "").strip()
        model = (models[index] if index < len(models) else "").strip()
        if make or model:
            rows.append({"make": make, "model": model})
    if not rows:
        return [{"make": "", "model": ""}]
    return rows


def sanitize_vehicle_rows(
    rows: list[dict[str, str]],
    make_model_options: dict[str, Any],
) -> list[dict[str, str]]:
    valid_makes = set(make_model_options.get("makes") or [])
    model_map = make_model_options.get("modelMap") or {}
    sanitized: list[dict[str, str]] = []

    for row in rows:
        make = (row.get("make") or "").strip()
        model = (row.get("model") or "").strip()
        if is_blocked_make(make):
            continue
        if make and make not in valid_makes:
            make = ""
            model = ""
        if model:
            valid_models = model_map.get(make, [])
            if not make or model not in valid_models:
                model = ""
        if model and not make:
            model = ""
        if make or model:
            sanitized.append({"make": make, "model": model})

    return sanitized or [{"make": "", "model": ""}]


def build_make_model_options(listings: list[dict[str, Any]]) -> dict[str, Any]:
    model_map: dict[str, set[str]] = {}
    make_counts: Counter[str] = Counter()

    for item in listings:
        make, model = listing_make_model(item)
        if not make or make == "—" or is_blocked_make(make):
            continue
        make_counts[make] += 1
        if model:
            model_map.setdefault(make, set()).add(model)

    makes = sorted(make_counts.keys(), key=str.casefold)
    return {
        "makes": makes,
        "modelMap": {
            make: sorted(models, key=str.casefold)
            for make, models in sorted(model_map.items(), key=lambda pair: pair[0].casefold())
        },
        "makeCounts": dict(make_counts),
    }


def build_year_options(listings: list[dict[str, Any]]) -> list[int]:
    years = {year for item in listings if (year := listing_year(item)) is not None}
    return sorted(years, reverse=True)


def _row_matches(item: dict[str, Any], row: dict[str, str]) -> bool:
    item_make, item_model = listing_make_model(item)
    make = (row.get("make") or "").strip()
    model = (row.get("model") or "").strip()
    if make and item_make.casefold() != make.casefold():
        return False
    if model and item_model.casefold() != model.casefold():
        return False
    return True


def filter_by_vehicle_rows(
    listings: list[dict[str, Any]],
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    active_rows = [row for row in rows if (row.get("make") or "").strip() or (row.get("model") or "").strip()]
    if not active_rows:
        return listings
    return [item for item in listings if any(_row_matches(item, row) for row in active_rows)]


def filter_by_year(
    listings: list[dict[str, Any]],
    *,
    year_from: int | None,
    year_to: int | None,
) -> list[dict[str, Any]]:
    if year_from is None and year_to is None:
        return listings
    filtered: list[dict[str, Any]] = []
    for item in listings:
        year = listing_year(item)
        if year is None:
            continue
        if year_from is not None and year < year_from:
            continue
        if year_to is not None and year > year_to:
            continue
        filtered.append(item)
    return filtered
