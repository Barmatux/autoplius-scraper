"""Standalone Belarus customs calculator (personal import estimates)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any

from autoplius.customs_duty import (
    CustomsAgeBand,
    customs_duty_eur,
    duty_rate_eur_per_cm3,
    under_three_bracket_for_value,
)
from autoplius.myfin_rates import eur_usd_rate, usd_byn_rate
from autoplius.price_rb import (
    CUSTOMS_FEE_BYN,
    DECLARANT_FEE_BYN,
    EPTS_FEE_BYN,
    PREFERENTIAL_DUTY_FACTOR,
    UTILIZATION_FEE_BYN,
)

# Пост. Совмина №195 от 23.04.2026 — личное пользование, категория M1.
UTILIZATION_FEE_UNDER_3_BYN = 624.92
UTILIZATION_FEE_OVER_3_BYN = UTILIZATION_FEE_BYN  # 1282.02

# Квота беспошлинного ввоза электромобилей для РБ на 2026 исчерпана (ГТК, сент. 2026).
EV_IMPORT_DUTY_RATE = 0.15
# Последовательные гибриды (EREV): ставка 15% (льгота только на «чистые» BEV).
EREV_IMPORT_DUTY_RATE = 0.15
VAT_RATE = 0.20

AGE_BAND_LABELS = {
    CustomsAgeBand.UNDER_THREE: "менее 3 лет",
    CustomsAgeBand.THREE_TO_FIVE: "от 3 до 5 лет",
    CustomsAgeBand.OVER_FIVE: "более 5 лет",
}

_RU_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


class VehicleKind(str, Enum):
    ICE = "ice"  # бензин/дизель и гибриды PHEV с ДВС (объём)
    ELECTRIC = "electric"
    EREV = "erev"


class PersonType(str, Enum):
    INDIVIDUAL = "individual"
    LEGAL = "legal"


def calculator_title_date(today: date | None = None) -> str:
    """E.g. «11 сентября» for the H1 with the current calendar day."""
    d = today or date.today()
    return f"{d.day} {_RU_MONTHS[d.month - 1]}"


def calculator_page_title(today: date | None = None) -> str:
    d = today or date.today()
    return f"Таможенный калькулятор для физлиц на {calculator_title_date(d)} {d.year} года"


def parse_age_band(value: str | CustomsAgeBand) -> CustomsAgeBand:
    if isinstance(value, CustomsAgeBand):
        return value
    key = str(value).strip().lower().replace("-", "_")
    aliases = {
        "under_3": CustomsAgeBand.UNDER_THREE,
        "under3": CustomsAgeBand.UNDER_THREE,
        "0": CustomsAgeBand.UNDER_THREE,
        "3_5": CustomsAgeBand.THREE_TO_FIVE,
        "3-5": CustomsAgeBand.THREE_TO_FIVE,
        "1": CustomsAgeBand.THREE_TO_FIVE,
        "over_5": CustomsAgeBand.OVER_FIVE,
        "over5": CustomsAgeBand.OVER_FIVE,
        "2": CustomsAgeBand.OVER_FIVE,
    }
    if key in aliases:
        return aliases[key]
    return CustomsAgeBand(key)


def utilization_fee_byn(*, age_band: CustomsAgeBand, person: PersonType) -> float:
    if person != PersonType.INDIVIDUAL:
        # Юрлица платят полные ставки — в калькуляторе не оцениваем.
        return UTILIZATION_FEE_OVER_3_BYN
    if age_band == CustomsAgeBand.UNDER_THREE:
        return UTILIZATION_FEE_UNDER_3_BYN
    return UTILIZATION_FEE_OVER_3_BYN


@dataclass(frozen=True)
class CustomsCalculatorResult:
    ok: bool
    error: str | None
    person: str
    vehicle_kind: str
    age_band: str
    age_band_label: str
    price_eur: float
    engine_cm3: int | None
    privilege_applied: bool
    duty_full_eur: float
    duty_payable_eur: float
    vat_eur: float
    duty_rate_label: str
    utilization_byn: float
    customs_fee_byn: float
    declarant_byn: float
    epts_byn: float
    fees_byn: float
    fees_eur: float
    fees_usd: float
    payments_eur: float
    payments_byn: float
    payments_usd: float
    total_eur: float
    total_usd: float
    total_byn: float
    eur_usd: float
    usd_byn: float
    eur_byn: float
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notes"] = list(self.notes)
        return data


def _fmt_rate_label(
    *,
    age_band: CustomsAgeBand,
    engine_cm3: int,
    price_eur: float,
    privilege: bool,
) -> str:
    if age_band == CustomsAgeBand.UNDER_THREE:
        bracket = under_three_bracket_for_value(price_eur)
        pct = int(round(bracket.percent * 100))
        base = f"{pct}% стоимости, но не менее {bracket.min_eur_per_cm3} €/см³"
    else:
        rate = duty_rate_eur_per_cm3(engine_cm3, age_band=age_band)
        base = f"{rate} €/см³"
    if privilege:
        return f"{base} (льгота Указ №140 −50%)"
    return base


def estimate_customs(
    *,
    price_eur: float,
    age_band: CustomsAgeBand | str,
    vehicle_kind: VehicleKind | str = VehicleKind.ICE,
    person: PersonType | str = PersonType.INDIVIDUAL,
    engine_cm3: int | None = None,
    privilege_50: bool = True,
) -> CustomsCalculatorResult:
    """Estimate personal-import customs payments for Belarus (orientational)."""
    try:
        band = parse_age_band(age_band)
        if isinstance(vehicle_kind, VehicleKind):
            kind = vehicle_kind
        else:
            kind = VehicleKind(str(vehicle_kind).strip().lower())
        if isinstance(person, PersonType):
            person_type = person
        else:
            person_type = PersonType(str(person).strip().lower())
    except ValueError:
        return CustomsCalculatorResult(
            ok=False,
            error="Проверьте параметры расчёта.",
            person=str(person),
            vehicle_kind=str(vehicle_kind),
            age_band=str(age_band),
            age_band_label="",
            price_eur=0.0,
            engine_cm3=engine_cm3,
            privilege_applied=False,
            duty_full_eur=0.0,
            duty_payable_eur=0.0,
            vat_eur=0.0,
            duty_rate_label="",
            utilization_byn=0.0,
            customs_fee_byn=0.0,
            declarant_byn=0.0,
            epts_byn=0.0,
            fees_byn=0.0,
            fees_eur=0.0,
            fees_usd=0.0,
            payments_eur=0.0,
            payments_byn=0.0,
            payments_usd=0.0,
            total_eur=0.0,
            total_usd=0.0,
            total_byn=0.0,
            eur_usd=0.0,
            usd_byn=0.0,
            eur_byn=0.0,
            notes=(),
        )

    eur_usd = eur_usd_rate()
    usd_byn = usd_byn_rate()
    eur_byn = eur_usd * usd_byn

    def fail(message: str) -> CustomsCalculatorResult:
        return CustomsCalculatorResult(
            ok=False,
            error=message,
            person=person_type.value,
            vehicle_kind=kind.value,
            age_band=band.value,
            age_band_label=AGE_BAND_LABELS[band],
            price_eur=float(price_eur or 0),
            engine_cm3=engine_cm3,
            privilege_applied=False,
            duty_full_eur=0.0,
            duty_payable_eur=0.0,
            vat_eur=0.0,
            duty_rate_label="",
            utilization_byn=0.0,
            customs_fee_byn=0.0,
            declarant_byn=0.0,
            epts_byn=0.0,
            fees_byn=0.0,
            fees_eur=0.0,
            fees_usd=0.0,
            payments_eur=0.0,
            payments_byn=0.0,
            payments_usd=0.0,
            total_eur=0.0,
            total_usd=0.0,
            total_byn=0.0,
            eur_usd=eur_usd,
            usd_byn=usd_byn,
            eur_byn=eur_byn,
            notes=(),
        )

    if person_type == PersonType.LEGAL:
        return fail(
            "Калькулятор считает платежи для физического лица при ввозе для личного "
            "пользования. Для юридических лиц ставки (пошлина, акциз, НДС, утильсбор) "
            "другие — напишите нам для точного расчёта."
        )

    try:
        raw_price = price_eur
        if raw_price is None or raw_price == "":
            price = 0.0
        else:
            price = float(raw_price)
    except (TypeError, ValueError):
        return fail("Укажите стоимость автомобиля в евро.")

    price_required = band == CustomsAgeBand.UNDER_THREE
    if price_required and price <= 0:
        return fail("Укажите стоимость автомобиля в евро.")
    if price < 0:
        return fail("Укажите стоимость автомобиля в евро.")
    if kind in (VehicleKind.ELECTRIC, VehicleKind.EREV) and price <= 0:
        return fail(
            "Для электромобилей и EREV укажите возраст «менее 3 лет» и стоимость авто в евро, "
            "либо выберите топливный автомобиль."
        )

    notes: list[str] = [
        "Расчёт для физлица при ввозе для личного пользования. "
        "Итоговая сумма на таможне зависит от документов и курса на день оформления.",
    ]

    duty_full = 0.0
    duty_payable = 0.0
    vat = 0.0
    privilege = False
    rate_label = ""
    cm3: int | None = None

    if kind == VehicleKind.ICE:
        try:
            cm3 = int(engine_cm3 or 0)
        except (TypeError, ValueError):
            return fail("Укажите рабочий объём двигателя в см³.")
        if cm3 <= 0:
            return fail("Укажите рабочий объём двигателя в см³.")
        duty_full = customs_duty_eur(cm3, age_band=band, customs_value_eur=price)
        privilege = bool(privilege_50)
        duty_payable = duty_full * (PREFERENTIAL_DUTY_FACTOR if privilege else 1.0)
        rate_label = _fmt_rate_label(
            age_band=band, engine_cm3=cm3, price_eur=price, privilege=privilege
        )
        if privilege:
            notes.append(
                "Льгота 50% по Указу Президента РБ №140 применяется при соответствии "
                "условиям указа (проверьте актуальные критерии)."
            )
    elif kind == VehicleKind.ELECTRIC:
        duty_full = price * EV_IMPORT_DUTY_RATE
        duty_payable = duty_full
        rate_label = f"{int(EV_IMPORT_DUTY_RATE * 100)}% таможенной стоимости (квота 0% исчерпана)"
        # НДС 0% для электромобилей не старше 5 лет (Указ №428, до 31.12.2028).
        if band == CustomsAgeBand.OVER_FIVE:
            vat = (price + duty_payable) * VAT_RATE
            notes.append("Для электромобилей старше 5 лет НДС считается по общей ставке 20%.")
        else:
            vat = 0.0
            notes.append(
                "НДС 0% для электромобилей с датой выпуска не более 5 лет "
                "(льгота по Указу №428, до 31.12.2028)."
            )
        notes.append(
            "С сентября 2026 квота беспошлинного ввоза электромобилей исчерпана — "
            "пошлина 15% от стоимости (разъяснения ГТК)."
        )
    elif kind == VehicleKind.EREV:
        duty_full = price * EREV_IMPORT_DUTY_RATE
        duty_payable = duty_full
        vat = (price + duty_payable) * VAT_RATE
        rate_label = (
            f"{int(EREV_IMPORT_DUTY_RATE * 100)}% стоимости + НДС "
            f"{int(VAT_RATE * 100)}% (последовательный гибрид EREV)"
        )
        notes.append(
            "С 2026 для последовательных гибридов (EREV) применяется пошлина 15%; "
            "льгота 0% сохраняется только для «чистых» электромобилей."
        )
    else:
        return fail("Неизвестный тип автомобиля.")

    util = utilization_fee_byn(age_band=band, person=person_type)
    customs_fee = CUSTOMS_FEE_BYN
    declarant = DECLARANT_FEE_BYN
    epts = EPTS_FEE_BYN
    fees_byn = util + customs_fee + declarant + epts
    fees_eur = fees_byn / eur_byn if eur_byn else 0.0
    fees_usd = fees_byn / usd_byn if usd_byn else 0.0

    payments_eur = duty_payable + vat + fees_eur
    payments_byn = (duty_payable + vat) * eur_byn + fees_byn
    payments_usd = payments_byn / usd_byn if usd_byn else 0.0

    total_eur = price + payments_eur
    total_byn = price * eur_byn + payments_byn
    total_usd = total_byn / usd_byn if usd_byn else 0.0

    return CustomsCalculatorResult(
        ok=True,
        error=None,
        person=person_type.value,
        vehicle_kind=kind.value,
        age_band=band.value,
        age_band_label=AGE_BAND_LABELS[band],
        price_eur=price,
        engine_cm3=cm3,
        privilege_applied=privilege,
        duty_full_eur=round(duty_full, 2),
        duty_payable_eur=round(duty_payable, 2),
        vat_eur=round(vat, 2),
        duty_rate_label=rate_label,
        utilization_byn=util,
        customs_fee_byn=customs_fee,
        declarant_byn=declarant,
        epts_byn=epts,
        fees_byn=round(fees_byn, 2),
        fees_eur=round(fees_eur, 2),
        fees_usd=round(fees_usd, 2),
        payments_eur=round(payments_eur, 2),
        payments_byn=round(payments_byn, 2),
        payments_usd=round(payments_usd, 2),
        total_eur=round(total_eur, 2),
        total_usd=round(total_usd, 2),
        total_byn=round(total_byn, 2),
        eur_usd=round(eur_usd, 4),
        usd_byn=round(usd_byn, 4),
        eur_byn=round(eur_byn, 4),
        notes=tuple(notes),
    )
