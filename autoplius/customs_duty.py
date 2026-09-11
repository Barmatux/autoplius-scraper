"""Customs duty rates for personal import of passenger cars into Belarus.

Source: Decision of the EEC Council No. 107 of 20.12.2017 (Annex 2, Table 2),
unified rates for personal-use motor vehicles (HS 8703).

- Under 3 years: max(% of customs value, €/cm³ floor) by value bracket.
- 3–5 and over 5 years: €/cm³ by engine volume only.

Volume brackets use inclusive upper bounds, matching official wording:
  «до 1000 см³», «от 1001 до 1500 см³», «от 1501 до 1800 см³», etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CustomsAgeBand(str, Enum):
    UNDER_THREE = "under_3"
    THREE_TO_FIVE = "3_5"
    OVER_FIVE = "over_5"


@dataclass(frozen=True)
class VolumeDutyBracket:
    max_cm3: int
    rate_eur_per_cm3: float


@dataclass(frozen=True)
class UnderThreeValueBracket:
    """Inclusive upper bound of customs value in EUR."""

    max_value_eur: float
    percent: float
    min_eur_per_cm3: float


# Cars not more than 3 years old — % of value, but not less than €/cm³.
CUSTOMS_DUTY_RATES_UNDER_3_YEARS: tuple[UnderThreeValueBracket, ...] = (
    UnderThreeValueBracket(8_500, 0.54, 2.5),
    UnderThreeValueBracket(16_700, 0.48, 3.5),
    UnderThreeValueBracket(42_300, 0.48, 5.5),
    UnderThreeValueBracket(84_500, 0.48, 7.5),
    UnderThreeValueBracket(169_000, 0.48, 15.0),
    UnderThreeValueBracket(float("inf"), 0.48, 20.0),
)

# Cars from 3 to 5 years old (more than 3, not more than 5).
CUSTOMS_DUTY_RATES_3_TO_5_YEARS: tuple[VolumeDutyBracket, ...] = (
    VolumeDutyBracket(1000, 1.5),
    VolumeDutyBracket(1500, 1.7),
    VolumeDutyBracket(1800, 2.5),
    VolumeDutyBracket(2300, 2.7),
    VolumeDutyBracket(3000, 3.0),
    VolumeDutyBracket(999_999, 3.6),
)

# Cars older than 5 years.
CUSTOMS_DUTY_RATES_OVER_5_YEARS: tuple[VolumeDutyBracket, ...] = (
    VolumeDutyBracket(1000, 3.0),
    VolumeDutyBracket(1500, 3.2),
    VolumeDutyBracket(1800, 3.5),
    VolumeDutyBracket(2300, 4.8),
    VolumeDutyBracket(3000, 5.0),
    VolumeDutyBracket(999_999, 5.7),
)

RATES_BY_AGE_BAND: dict[CustomsAgeBand, tuple[VolumeDutyBracket, ...]] = {
    CustomsAgeBand.THREE_TO_FIVE: CUSTOMS_DUTY_RATES_3_TO_5_YEARS,
    CustomsAgeBand.OVER_FIVE: CUSTOMS_DUTY_RATES_OVER_5_YEARS,
}


def duty_rate_eur_per_cm3(engine_cm3: int, *, age_band: CustomsAgeBand) -> float:
    if age_band == CustomsAgeBand.UNDER_THREE:
        raise ValueError("under-3 duty uses percent/min €/cm³ brackets, not a flat €/cm³ rate")
    if engine_cm3 <= 0:
        raise ValueError("engine_cm3 must be positive")
    for bracket in RATES_BY_AGE_BAND[age_band]:
        if engine_cm3 <= bracket.max_cm3:
            return bracket.rate_eur_per_cm3
    return RATES_BY_AGE_BAND[age_band][-1].rate_eur_per_cm3


def under_three_duty_eur(engine_cm3: int, customs_value_eur: float) -> float:
    """Unified personal payment for cars not older than 3 years."""
    if engine_cm3 <= 0:
        raise ValueError("engine_cm3 must be positive")
    if customs_value_eur <= 0:
        raise ValueError("customs_value_eur must be positive")
    for bracket in CUSTOMS_DUTY_RATES_UNDER_3_YEARS:
        if customs_value_eur <= bracket.max_value_eur:
            by_value = customs_value_eur * bracket.percent
            by_volume = engine_cm3 * bracket.min_eur_per_cm3
            return max(by_value, by_volume)
    last = CUSTOMS_DUTY_RATES_UNDER_3_YEARS[-1]
    return max(customs_value_eur * last.percent, engine_cm3 * last.min_eur_per_cm3)


def under_three_bracket_for_value(customs_value_eur: float) -> UnderThreeValueBracket:
    for bracket in CUSTOMS_DUTY_RATES_UNDER_3_YEARS:
        if customs_value_eur <= bracket.max_value_eur:
            return bracket
    return CUSTOMS_DUTY_RATES_UNDER_3_YEARS[-1]


def customs_duty_eur(
    engine_cm3: int,
    *,
    age_band: CustomsAgeBand,
    customs_value_eur: float | None = None,
) -> float:
    """Full (pre-privilege) personal ICE/PHEV duty in EUR."""
    if age_band == CustomsAgeBand.UNDER_THREE:
        if customs_value_eur is None:
            raise ValueError("customs_value_eur is required for under-3 cars")
        return under_three_duty_eur(engine_cm3, customs_value_eur)
    rate = duty_rate_eur_per_cm3(engine_cm3, age_band=age_band)
    return float(engine_cm3 * rate)


def customs_age_band_from_months(age_months: int) -> CustomsAgeBand | None:
    """Map vehicle age in whole months to a volume €/cm³ bracket (cars older than 3 years).

    Listings younger than or equal to 3 years return None — catalog «Цена в РБ»
    does not estimate under-3 rates.
    """
    if age_months <= 36:
        return None
    if age_months <= 60:
        return CustomsAgeBand.THREE_TO_FIVE
    return CustomsAgeBand.OVER_FIVE
