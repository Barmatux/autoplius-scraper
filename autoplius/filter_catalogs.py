"""Static filter dropdown catalogs for the listings index.

Phase 1: body / fuel / transmission / volume / year no longer need SQL
aggregations on every cold render. Cities and make/model stay DB-backed.
"""

from __future__ import annotations

from datetime import date

from autoplius.catalog_filters import MIN_CATALOG_YEAR
from autoplius.spec_filters import format_volume_option

# Russian labels shown in UI (listings are localized on write/read).
BODY_TYPE_OPTIONS: tuple[str, ...] = (
    "Седан",
    "Хэтчбек",
    "Универсал",
    "Внедорожник / Кроссовер",
    "Внедорожник",
    "Кроссовер",
    "Минивэн",
    "Купе",
    "Кабриолет",
    "Лимузин",
    "Коммерческий",
    "Грузовой фургон",
    "Пассажирский микроавтобус",
    "Грузовой микроавтобус",
    "Пассажирский / грузовой микроавтобус",
)

FUEL_OPTIONS: tuple[str, ...] = (
    "Дизель",
    "Бензин",
    "Бензин / электричество",
    "Бензин / газ",
    "Дизель / электричество",
    "Электричество",
    "Газ",
    "Водород",
)

# Raw LT+RU strings used to map filter slugs → SQL IN values.
TRANSMISSION_RAW_VALUES: tuple[str, ...] = (
    "Автоматическая",
    "Automatinė",
    "Автоматическая / Tiptronic",
    "Automatinė / Tiptronic",
    "Механическая",
    "Mechaninė",
    "Механическая / 6 передач",
    "Mechaninė / 6 pavarų",
)

# Covers default ≤1.9 and wider range when the toggle is off.
_VOLUME_MIN = 1.0
_VOLUME_MAX = 3.0
_VOLUME_STEP = 0.1


def static_body_type_options() -> list[str]:
    return list(BODY_TYPE_OPTIONS)


def static_fuel_options() -> list[str]:
    return list(FUEL_OPTIONS)


def static_transmission_raw_values() -> list[str]:
    return list(TRANSMISSION_RAW_VALUES)


def static_volume_options(
    *,
    min_liters: float = _VOLUME_MIN,
    max_liters: float = _VOLUME_MAX,
    step: float = _VOLUME_STEP,
) -> list[str]:
    values: list[str] = []
    # Avoid float drift: iterate in tenths.
    start = int(round(min_liters * 10))
    stop = int(round(max_liters * 10))
    step_i = max(1, int(round(step * 10)))
    for tenths in range(start, stop + 1, step_i):
        values.append(format_volume_option(tenths / 10.0))
    return values


def static_year_options(
    *,
    min_year: int = MIN_CATALOG_YEAR,
    max_year: int | None = None,
) -> list[int]:
    end = max_year if max_year is not None else date.today().year
    if end < min_year:
        return []
    return list(range(end, min_year - 1, -1))
