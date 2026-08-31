"""Belarus landed price (Цена в РБ) estimate for catalog listings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autoplius.customs_duty import (
    CustomsAgeBand,
    customs_age_band_from_months,
    duty_rate_eur_per_cm3,
)
from autoplius.engine_volume import engine_volume_cm3
from autoplius.myfin_rates import eur_usd_rate, usd_byn_rate
from autoplius.passable_age import listing_age_months

# Fixed BYN fees for personal import (current schedule).
UTILIZATION_FEE_BYN = 1282.02
CUSTOMS_FEE_BYN = 120.0
DECLARANT_FEE_BYN = 230.0
EPTS_FEE_BYN = 80.0
FIXED_FEES_BYN = UTILIZATION_FEE_BYN + CUSTOMS_FEE_BYN + DECLARANT_FEE_BYN + EPTS_FEE_BYN

# Указ №140 — 50% preferential customs duty.
PREFERENTIAL_DUTY_FACTOR = 0.5

AGE_BAND_LABELS = {
    CustomsAgeBand.THREE_TO_FIVE: "3–5 лет",
    CustomsAgeBand.OVER_FIVE: "старше 5 лет",
}


def _fmt_money(value: float, decimals: int = 0) -> str:
    if decimals <= 0:
        return f"{int(round(value)):,}".replace(",", " ")
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


@dataclass(frozen=True)
class PriceRbBreakdown:
    total_usd: int
    price_eur: int
    engine_cm3: int
    age_band: CustomsAgeBand
    age_band_label: str
    duty_rate_eur_per_cm3: float
    duty_full_eur: float
    duty_preferential_eur: float
    car_plus_duty_eur: float
    car_plus_duty_usd: float
    eur_usd: float
    fees_byn: float
    fees_usd: float
    usd_byn: float
    utilization_byn: float = UTILIZATION_FEE_BYN
    customs_fee_byn: float = CUSTOMS_FEE_BYN
    declarant_byn: float = DECLARANT_FEE_BYN
    epts_byn: float = EPTS_FEE_BYN

    @property
    def total_formatted(self) -> str:
        return f"{_fmt_money(self.total_usd)} $"

    def tooltip_lines(self) -> list[str]:
        return [
            f"Цена в LT: {_fmt_money(self.price_eur)} €",
            f"Объём двигателя: {_fmt_money(self.engine_cm3)} см³",
            f"Возраст для ставки: {self.age_band_label}",
            f"Ставка: {self.duty_rate_eur_per_cm3} €/см³",
            f"Растаможка: {_fmt_money(self.duty_full_eur)} €",
            f"Льготная растаможка (÷2): {_fmt_money(self.duty_preferential_eur)} €",
            (
                f"LT + растаможка: {_fmt_money(self.car_plus_duty_eur)} € × {self.eur_usd:.4f} "
                f"= {_fmt_money(self.car_plus_duty_usd)} $"
            ),
            f"Утилизационный сбор: {_fmt_money(self.utilization_byn, 2)} Br",
            f"Таможенный сбор: {_fmt_money(self.customs_fee_byn, 2)} Br",
            f"Услуги декларантов: {_fmt_money(self.declarant_byn, 2)} Br",
            f"ЭПТС: {_fmt_money(self.epts_byn, 2)} Br",
            (
                f"Сборы: {_fmt_money(self.fees_byn, 2)} Br ÷ {self.usd_byn:.4f} "
                f"= {_fmt_money(self.fees_usd)} $"
            ),
            f"Итого в РБ: {_fmt_money(self.total_usd)} $",
        ]


def estimate_price_rb(item: dict[str, Any]) -> PriceRbBreakdown | None:
    price_eur = item.get("price_eur")
    if price_eur is None:
        return None
    try:
        price_eur_i = int(price_eur)
    except (TypeError, ValueError):
        return None

    engine_cm3 = engine_volume_cm3(item)
    if engine_cm3 is None:
        return None

    months = listing_age_months(item)
    if months is None:
        return None
    age_band = customs_age_band_from_months(months)
    if age_band is None:
        return None

    rate = duty_rate_eur_per_cm3(engine_cm3, age_band=age_band)
    duty_full = float(engine_cm3 * rate)
    duty_pref = duty_full * PREFERENTIAL_DUTY_FACTOR
    car_plus_duty_eur = price_eur_i + duty_pref

    eur_usd = eur_usd_rate()
    usd_byn = usd_byn_rate()
    car_plus_duty_usd = car_plus_duty_eur * eur_usd
    fees_usd = FIXED_FEES_BYN / usd_byn
    total_usd = int(round(car_plus_duty_usd + fees_usd))

    return PriceRbBreakdown(
        total_usd=total_usd,
        price_eur=price_eur_i,
        engine_cm3=engine_cm3,
        age_band=age_band,
        age_band_label=AGE_BAND_LABELS[age_band],
        duty_rate_eur_per_cm3=rate,
        duty_full_eur=duty_full,
        duty_preferential_eur=duty_pref,
        car_plus_duty_eur=car_plus_duty_eur,
        car_plus_duty_usd=car_plus_duty_usd,
        eur_usd=eur_usd,
        fees_byn=FIXED_FEES_BYN,
        fees_usd=fees_usd,
        usd_byn=usd_byn,
    )


def estimate_price_rb_usd(price_eur: int | None = None, *, item: dict[str, Any] | None = None) -> int | None:
    """Backward-compatible helper used by older call sites."""
    if item is None:
        return None
    breakdown = estimate_price_rb(item)
    return breakdown.total_usd if breakdown else None
