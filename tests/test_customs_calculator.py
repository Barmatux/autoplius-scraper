from __future__ import annotations

from datetime import date

import pytest

from autoplius.customs_calculator import (
    PersonType,
    VehicleKind,
    calculator_page_title,
    estimate_customs,
)
from autoplius.customs_duty import (
    CustomsAgeBand,
    customs_duty_eur,
    duty_rate_eur_per_cm3,
    under_three_duty_eur,
)


def test_duty_rate_3_to_5_brackets():
    assert duty_rate_eur_per_cm3(1000, age_band=CustomsAgeBand.THREE_TO_FIVE) == 1.5
    assert duty_rate_eur_per_cm3(1001, age_band=CustomsAgeBand.THREE_TO_FIVE) == 1.7
    assert duty_rate_eur_per_cm3(1496, age_band=CustomsAgeBand.THREE_TO_FIVE) == 1.7
    assert duty_rate_eur_per_cm3(1800, age_band=CustomsAgeBand.THREE_TO_FIVE) == 2.5


def test_duty_rate_over_5_brackets():
    assert duty_rate_eur_per_cm3(1496, age_band=CustomsAgeBand.OVER_FIVE) == 3.2
    assert duty_rate_eur_per_cm3(3001, age_band=CustomsAgeBand.OVER_FIVE) == 5.7


def test_under_three_uses_percent_or_volume_floor():
    # 8000 €, 1496 cm³ → max(8000*0.54, 1496*2.5) = max(4320, 3740) = 4320
    assert under_three_duty_eur(1496, 8000) == pytest.approx(4320.0)
    # With 50% privilege matches common calculator examples: 2160
    assert customs_duty_eur(1496, age_band=CustomsAgeBand.UNDER_THREE, customs_value_eur=8000) == pytest.approx(
        4320.0
    )


def test_three_to_five_volume_duty_matches_known_example():
    # 1496 × 1.7 = 2543.2; privilege 50% → 1271.6
    full = customs_duty_eur(1496, age_band=CustomsAgeBand.THREE_TO_FIVE)
    assert full == pytest.approx(2543.2)


def test_estimate_ice_with_privilege(monkeypatch):
    monkeypatch.setattr("autoplius.customs_calculator.eur_usd_rate", lambda: 1.164)
    monkeypatch.setattr("autoplius.customs_calculator.usd_byn_rate", lambda: 3.04)

    result = estimate_customs(
        price_eur=10_000,
        age_band=CustomsAgeBand.THREE_TO_FIVE,
        vehicle_kind=VehicleKind.ICE,
        engine_cm3=1496,
        privilege_50=True,
    )
    assert result.ok
    assert result.duty_full_eur == pytest.approx(2543.2)
    assert result.duty_payable_eur == pytest.approx(1271.6)
    assert result.utilization_byn == pytest.approx(1282.02)
    assert result.privilege_applied is True
    assert result.total_eur > 10_000


def test_estimate_under_three_privilege(monkeypatch):
    monkeypatch.setattr("autoplius.customs_calculator.eur_usd_rate", lambda: 1.0)
    monkeypatch.setattr("autoplius.customs_calculator.usd_byn_rate", lambda: 3.0)

    result = estimate_customs(
        price_eur=8000,
        age_band="under_3",
        engine_cm3=1496,
        privilege_50=True,
    )
    assert result.ok
    assert result.duty_payable_eur == pytest.approx(2160.0)
    assert result.utilization_byn == pytest.approx(624.92)


def test_estimate_electric_over_quota(monkeypatch):
    monkeypatch.setattr("autoplius.customs_calculator.eur_usd_rate", lambda: 1.0)
    monkeypatch.setattr("autoplius.customs_calculator.usd_byn_rate", lambda: 3.0)

    young = estimate_customs(
        price_eur=20_000,
        age_band=CustomsAgeBand.UNDER_THREE,
        vehicle_kind=VehicleKind.ELECTRIC,
        privilege_50=False,
    )
    assert young.ok
    assert young.duty_payable_eur == pytest.approx(3000.0)  # 15%
    assert young.vat_eur == 0.0

    old = estimate_customs(
        price_eur=20_000,
        age_band=CustomsAgeBand.OVER_FIVE,
        vehicle_kind=VehicleKind.ELECTRIC,
    )
    assert old.ok
    assert old.vat_eur == pytest.approx((20_000 + 3000) * 0.2)


def test_estimate_rejects_legal_entity():
    result = estimate_customs(
        price_eur=10_000,
        age_band=CustomsAgeBand.THREE_TO_FIVE,
        person=PersonType.LEGAL,
        engine_cm3=1500,
    )
    assert not result.ok
    assert result.error


def test_estimate_ice_older_without_price(monkeypatch):
    monkeypatch.setattr("autoplius.customs_calculator.eur_usd_rate", lambda: 1.0)
    monkeypatch.setattr("autoplius.customs_calculator.usd_byn_rate", lambda: 3.0)

    result = estimate_customs(
        price_eur=0,
        age_band=CustomsAgeBand.THREE_TO_FIVE,
        engine_cm3=1496,
        privilege_50=True,
    )
    assert result.ok
    assert result.price_eur == 0
    assert result.duty_payable_eur == pytest.approx(1271.6)


def test_page_title_includes_date():
    title = calculator_page_title(date(2026, 9, 11))
    assert title == "Таможенный калькулятор для физлиц на 11 сентября 2026 года"
