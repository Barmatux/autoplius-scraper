"""Merged spec rows for listing detail page."""

from __future__ import annotations

import re
from typing import Any

from autoplius.engine_volume import (
    ENGINE_CM3_RE,
    VOLUME_PARAM_KEY_MARKERS,
    engine_volume_liters,
    _parse_volume_cm3_from_text,
)
from autoplius.labels import PARAMETER_TO_FIELD, resolve_listing_mileage_km

_SKIP_PARAM_LABEL_RE = re.compile(
    r"(co[\s₂2]?|выброс|emisij|"
    r"id\s*объяв|skelbimo\s*id|"
    r"регистр|registracij|mokestis|взнос|"
    r"проверьте|истори)",
    re.I,
)
_SKIP_PARAM_VALUE_RE = re.compile(r"(проверьте|»|https?://|autoplius)", re.I)

_CORE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("year", "Год", "text"),
    ("mileage_km", "Пробег", "mileage"),
    ("transmission", "КПП", "text"),
    ("body_type", "Кузов", "text"),
    ("city", "Город", "text"),
    ("vin_masked", "VIN", "mono"),
    ("phone", "Телефон", "phone"),
)

_ENGINE_PARAM_KEYS = ("Двигатель", "Variklis")
_FUEL_PARAM_KEYS = ("Тип топлива", "Kuro tipas")


def _norm_value(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _norm_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _values_equivalent(field: str, left: str, right: str) -> bool:
    if field == "mileage_km":
        return _norm_digits(left) == _norm_digits(right) and bool(_norm_digits(left))
    return _norm_value(left) == _norm_value(right)


def _skip_param_label(label: str) -> bool:
    return bool(_SKIP_PARAM_LABEL_RE.search(label or ""))


def _skip_param_value(value: str) -> bool:
    return bool(_SKIP_PARAM_VALUE_RE.search(value or ""))


def _is_merged_engine_param(label: str) -> bool:
    folded = (label or "").casefold()
    if label in _ENGINE_PARAM_KEYS or label in _FUEL_PARAM_KEYS:
        return True
    if any(marker in folded for marker in ("топлив", "fuel", "kuro tip")):
        return True
    return any(marker in folded for marker in VOLUME_PARAM_KEY_MARKERS)


def _format_liters_short(liters: float) -> str:
    rounded = round(liters, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}".rstrip("0").rstrip(".")


def _parse_engine_param(text: str) -> tuple[int | None, str | None]:
    cm3 = _parse_volume_cm3_from_text(text)
    match = ENGINE_CM3_RE.search(text)
    if match:
        rest = text[match.end() :].strip(" ,;")
        return cm3, rest or None
    return cm3, text.strip() or None


def _detail_engine_line(item: dict[str, Any]) -> str | None:
    params = item.get("parameters") or {}
    fuel = (item.get("fuel") or "").strip()
    if not fuel:
        for key in _FUEL_PARAM_KEYS:
            fuel = str(params.get(key) or "").strip()
            if fuel:
                break

    liters = engine_volume_liters(item)
    cm3: int | None = None
    power: str | None = None
    for key in _ENGINE_PARAM_KEYS:
        raw = str(params.get(key) or "").strip()
        if not raw:
            continue
        parsed_cm3, parsed_power = _parse_engine_param(raw)
        if parsed_cm3 is not None:
            cm3 = parsed_cm3
        if parsed_power:
            power = parsed_power
        break

    if cm3 is None and liters is not None:
        cm3 = int(round(liters * 1000))

    chunks: list[str] = []
    if fuel:
        chunks.append(fuel)
    if liters is not None:
        chunks.append(f"{_format_liters_short(liters)}л")
    line = " ".join(chunks)
    if cm3 is not None:
        line = f"{line} ({cm3} см³)".strip() if line else f"({cm3} см³)"
    if power:
        line = f"{line} {power}".strip() if line else power
    return line or None


def _field_value(item: dict[str, Any], field: str) -> str | None:
    if field == "mileage_km":
        mileage = resolve_listing_mileage_km(item)
        if mileage is None:
            return None
        return f"{int(mileage):,}".replace(",", " ") + " km"
    value = item.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def detail_spec_rows(item: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    shown_values: set[str] = set()

    engine_line = _detail_engine_line(item)
    if engine_line:
        shown_values.add(_norm_value(engine_line))
        shown_values.add(_norm_value(item.get("fuel")))
        for key in _ENGINE_PARAM_KEYS:
            shown_values.add(_norm_value((item.get("parameters") or {}).get(key)))

    for field, label, kind in _CORE_FIELDS:
        value = _field_value(item, field)
        if not value:
            continue
        shown_values.add(_norm_value(value))
        kind = "city" if field == "city" else kind
        rows.append({"label": label, "value": value, "kind": kind})
        if field == "mileage_km" and engine_line:
            rows.append({"label": "Двигатель", "value": engine_line, "kind": "text"})
            engine_line = None

    if engine_line:
        rows.insert(min(2, len(rows)), {"label": "Двигатель", "value": engine_line, "kind": "text"})

    for param_label, param_value in (item.get("parameters") or {}).items():
        if _skip_param_label(param_label) or _is_merged_engine_param(param_label):
            continue
        value = str(param_value or "").strip()
        if not value or _skip_param_value(value):
            continue
        mapped_field = PARAMETER_TO_FIELD.get(param_label)
        if mapped_field:
            existing = _field_value(item, mapped_field)
            if existing and _values_equivalent(mapped_field, existing, value):
                continue
        if _norm_value(value) in shown_values:
            continue
        shown_values.add(_norm_value(value))
        kind = "mono" if "vin" in param_label.casefold() else "text"
        rows.append({"label": param_label, "value": value, "kind": kind})

    return rows
