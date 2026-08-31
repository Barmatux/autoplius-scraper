from __future__ import annotations

from typing import Any

from autoplius.passable_age import parse_registration_date

MIN_CATALOG_YEAR = 2008
HIDDEN_MAKES = frozenset({"skoda"})


def listing_make(item: dict[str, Any]) -> str | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    make = title.split(",", 1)[0].strip().split()[0]
    return make.lower().replace("š", "s")


def listing_year(item: dict[str, Any]) -> int | None:
    parsed = parse_registration_date(item.get("year"))
    if parsed:
        return parsed[0]

    params = item.get("parameters") or {}
    for key in ("Pirma registracija", "Первая регистрация", "Год выпуска"):
        parsed = parse_registration_date(params.get(key))
        if parsed:
            return parsed[0]

    parsed = parse_registration_date(item.get("title"))
    return parsed[0] if parsed else None


def is_catalog_visible(item: dict[str, Any]) -> bool:
    make = listing_make(item)
    if make in HIDDEN_MAKES:
        return False

    year = listing_year(item)
    if year is not None and year < MIN_CATALOG_YEAR:
        return False

    return True
