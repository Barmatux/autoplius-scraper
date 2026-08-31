from __future__ import annotations

import re
from typing import Any

ENGINE_LITERS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*l(?:\b|\.)", re.I)
ENGINE_CM3_RE = re.compile(r"(\d{3,5})\s*cm(?:³|3)", re.I)
ENGINE_BEFORE_CODE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s+(?:l\b|TDI|TFSI|TSI|HDI|CDI|Twin|Turbo|varikli)",
    re.I,
)


def _format_liters(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))} л"
    return f"{value:.1f}".replace(".", ",") + " л"


def _parse_volume_liters_from_text(text: str) -> float | None:
    normalized = text.replace("\xa0", " ")
    match = ENGINE_LITERS_RE.search(normalized)
    if match:
        liters = float(match.group(1).replace(",", "."))
        if 0.5 <= liters <= 10.0:
            return liters
    match = ENGINE_CM3_RE.search(normalized)
    if match:
        cm3 = int(match.group(1))
        if 500 <= cm3 <= 10000:
            return cm3 / 1000
    match = ENGINE_BEFORE_CODE_RE.search(normalized)
    if match:
        liters = float(match.group(1).replace(",", "."))
        if 0.5 <= liters <= 10.0:
            return liters
    return None


def engine_volume_liters(item: dict[str, Any]) -> float | None:
    cm3 = engine_volume_cm3(item)
    if cm3 is None:
        return None
    return cm3 / 1000


def engine_volume_cm3(item: dict[str, Any]) -> int | None:
    """Exact engine displacement in cm³ when parseable."""
    for key in ("description_ru", "description", "engine", "title"):
        value = item.get(key)
        if not value:
            continue
        cm3 = _parse_volume_cm3_from_text(str(value))
        if cm3 is not None:
            return cm3

    params = item.get("parameters") or {}
    for param_key in ("Variklis", "Двигатель", "Darbinis tūris", "Рабочий объем"):
        value = params.get(param_key)
        if not value:
            continue
        cm3 = _parse_volume_cm3_from_text(str(value))
        if cm3 is not None:
            return cm3
    return None


def _parse_volume_cm3_from_text(text: str) -> int | None:
    normalized = text.replace("\xa0", " ")
    match = ENGINE_CM3_RE.search(normalized)
    if match:
        cm3 = int(match.group(1))
        if 500 <= cm3 <= 10000:
            return cm3

    liters = None
    match = ENGINE_LITERS_RE.search(normalized)
    if match:
        liters = float(match.group(1).replace(",", "."))
    else:
        match = ENGINE_BEFORE_CODE_RE.search(normalized)
        if match:
            liters = float(match.group(1).replace(",", "."))
    if liters is not None and 0.5 <= liters <= 10.0:
        return int(round(liters * 1000))
    return None


def engine_volume_from_listing(item: dict[str, Any]) -> str | None:
    liters = engine_volume_liters(item)
    if liters is None:
        return None
    return _format_liters(liters)
