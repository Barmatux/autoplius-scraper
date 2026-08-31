from __future__ import annotations

import re

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


def promote_parameters(row: dict, parameters: dict[str, str]) -> None:
    for src, dst in PARAMETER_TO_FIELD.items():
        value = parameters.get(src)
        if not value or row.get(dst):
            continue
        if dst == "mileage_km":
            digits = "".join(ch for ch in value if ch.isdigit())
            row["mileage_km"] = int(digits) if digits else row.get("mileage_km")
        else:
            row[dst] = value
