"""Merged spec rows for listing detail page."""

from __future__ import annotations

import re
from typing import Any

from autoplius.labels import PARAMETER_TO_FIELD

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
    ("fuel", "Топливо", "text"),
    ("transmission", "КПП", "text"),
    ("body_type", "Кузов", "text"),
    ("engine", "Двигатель", "text"),
    ("city", "Город", "text"),
    ("vin_masked", "VIN", "mono"),
    ("phone", "Телефон", "phone"),
)


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


def _field_value(item: dict[str, Any], field: str) -> str | None:
    if field == "mileage_km":
        mileage = item.get("mileage_km")
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

    for field, label, kind in _CORE_FIELDS:
        value = _field_value(item, field)
        if not value:
            continue
        shown_values.add(_norm_value(value))
        rows.append({"label": label, "value": value, "kind": kind})

    for param_label, param_value in (item.get("parameters") or {}).items():
        if _skip_param_label(param_label):
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
