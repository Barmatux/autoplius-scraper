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


def _parse_volume_from_text(text: str) -> str | None:
    normalized = text.replace("\xa0", " ")
    match = ENGINE_LITERS_RE.search(normalized)
    if match:
        liters = float(match.group(1).replace(",", "."))
        if 0.5 <= liters <= 10.0:
            return _format_liters(liters)
    match = ENGINE_CM3_RE.search(normalized)
    if match:
        cm3 = int(match.group(1))
        if 500 <= cm3 <= 10000:
            return _format_liters(cm3 / 1000)
    match = ENGINE_BEFORE_CODE_RE.search(normalized)
    if match:
        liters = float(match.group(1).replace(",", "."))
        if 0.5 <= liters <= 10.0:
            return _format_liters(liters)
    return None


def engine_volume_from_listing(item: dict[str, Any]) -> str | None:
    for key in ("description_ru", "description"):
        value = item.get(key)
        if not value:
            continue
        volume = _parse_volume_from_text(str(value))
        if volume:
            return volume

    for key in ("engine", "title"):
        value = item.get(key)
        if not value:
            continue
        volume = _parse_volume_from_text(str(value))
        if volume:
            return volume

    params = item.get("parameters") or {}
    for param_key in ("Variklis", "Двигатель"):
        value = params.get(param_key)
        if not value:
            continue
        volume = _parse_volume_from_text(str(value))
        if volume:
            return volume
    return None
