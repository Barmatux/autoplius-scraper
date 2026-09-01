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


MIN_CATALOG_YEAR = 2008
HIDDEN_MAKES = frozenset({"skoda"})
PICKUP_BODY_TYPES = frozenset({"pikapas", "pikap", "pickup", "пикап"})


def is_pickup_body_type(body_type: str | None) -> bool:
    text = (body_type or "").strip().casefold()
    if not text:
        return False
    if text in PICKUP_BODY_TYPES:
        return True
    return "pikap" in text or "pickup" in text


def is_pickup_listing(item: dict[str, Any]) -> bool:
    if is_pickup_body_type(item.get("body_type")):
        return True
    params = item.get("parameters") or {}
    for key in ("Kėbulo tipas", "Тип кузова", "body_type"):
        if is_pickup_body_type(params.get(key) if isinstance(params.get(key), str) else None):
            return True
    return False


def is_catalog_visible(item: dict[str, Any]) -> bool:
    if is_pickup_listing(item):
        return False

    make = listing_make(item)
    if make in HIDDEN_MAKES:
        return False

    year = listing_year(item)
    if year is not None and year < MIN_CATALOG_YEAR:
        return False

    return True
