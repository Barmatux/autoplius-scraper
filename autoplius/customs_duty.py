"""Customs duty rates per cm³ for personal import of passenger cars into Belarus.

Applies to cars older than 3 years under the EAEU unified rates
(Совет ЕЭК, решение № 107 от 20.12.2017).

Duty = engine volume (cm³) × rate (EUR per cm³).

Volume brackets use inclusive upper bounds, matching official wording:
  «до 1000 см³», «от 1001 до 1500 см³», «от 1501 до 1800 см³», etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CustomsAgeBand(str, Enum):
    THREE_TO_FIVE = "3_5"
    OVER_FIVE = "over_5"


@dataclass(frozen=True)
class VolumeDutyBracket:
    max_cm3: int
    rate_eur_per_cm3: float


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
    if engine_cm3 <= 0:
        raise ValueError("engine_cm3 must be positive")
    for bracket in RATES_BY_AGE_BAND[age_band]:
        if engine_cm3 <= bracket.max_cm3:
            return bracket.rate_eur_per_cm3
    return RATES_BY_AGE_BAND[age_band][-1].rate_eur_per_cm3


def customs_duty_eur(engine_cm3: int, *, age_band: CustomsAgeBand) -> int:
    rate = duty_rate_eur_per_cm3(engine_cm3, age_band=age_band)
    return int(round(engine_cm3 * rate))


def customs_age_band_from_months(age_months: int) -> CustomsAgeBand | None:
    """Map vehicle age in whole months to a customs bracket (cars older than 3 years)."""
    if age_months <= 36:
        return None
    if age_months <= 60:
        return CustomsAgeBand.THREE_TO_FIVE
    return CustomsAgeBand.OVER_FIVE
