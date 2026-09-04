from __future__ import annotations

import re
from typing import Any

# Map parameter labels (LT + RU) to listing top-level fields.
PARAMETER_TO_FIELD: dict[str, str] = {
    "Pirma registracija": "year",
    "Kuro tipas": "fuel",
    "Pavarų dėžė": "transmission",
    "Kėbulo tipas": "body_type",
    "Rida": "mileage_km",
    "Первая регистрация": "year",
    "Год выпуска": "year",
    "Тип топлива": "fuel",
    "Коробка передач": "transmission",
    "КПП": "transmission",
    "Тип кузова": "body_type",
    "Пробег": "mileage_km",
}

_MILEAGE_PARAM_KEYS = ("Пробег", "Rida", "Mileage")


def parse_mileage_km(value: Any) -> int | None:
    """Extract integer km from Autoplius mileage text (e.g. '134 728 км')."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if value < 0:
            return None
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def mileage_from_parameters(parameters: dict[str, Any] | None) -> int | None:
    if not parameters:
        return None
    for key in _MILEAGE_PARAM_KEYS:
        parsed = parse_mileage_km(parameters.get(key))
        if parsed is not None:
            return parsed
    for key, value in parameters.items():
        folded = str(key).casefold()
        if "пробег" in folded or folded == "rida" or "mileage" in folded:
            parsed = parse_mileage_km(value)
            if parsed is not None:
                return parsed
    return None


def resolve_listing_mileage_km(item: dict[str, Any] | None) -> int | None:
    """Prefer top-level mileage_km; fall back to parameters."""
    if not item:
        return None
    parsed = parse_mileage_km(item.get("mileage_km"))
    if parsed is not None:
        return parsed
    parameters = item.get("parameters")
    if isinstance(parameters, dict):
        return mileage_from_parameters(parameters)
    return None


def promote_parameters(row: dict, parameters: dict[str, str]) -> None:
    for src, dst in PARAMETER_TO_FIELD.items():
        value = parameters.get(src)
        if not value or row.get(dst):
            continue
        if dst == "mileage_km":
            parsed = parse_mileage_km(value)
            if parsed is not None:
                row["mileage_km"] = parsed
        else:
            row[dst] = value
