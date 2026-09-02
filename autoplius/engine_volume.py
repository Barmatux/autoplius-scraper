from __future__ import annotations

import re
from typing import Any

from autoplius.listing_display import listing_make_model

ENGINE_LITERS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:l|л)(?:\b|\.)", re.I)
ENGINE_CM3_RE = re.compile(r"(\d{3,5})\s*(?:cm|см)(?:³|3|\u00b3)?", re.I)
ENGINE_BEFORE_CODE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s+(?:l\b|TDI|TFSI|TSI|HDI|CDI|Twin|Turbo|varikli)",
    re.I,
)

CUSTOMS_NOMINAL_16_DIESEL_CM3 = 1560
CUSTOMS_NOMINAL_16_DIESEL_MAKES = frozenset({"peugeot", "citroen", "ford", "volvo"})
CUSTOMS_NOMINAL_13_PETROL_CM3 = 1332
CUSTOMS_NOMINAL_13_PETROL_MAKES = frozenset({"renault", "nissan", "mercedes"})
DIESEL_MARKERS = (
    "diesel",
    "dyzel",
    "дизел",
    "дизель",
    "hdi",
    "tdci",
    "tdi",
    "d4",
    "d3",
    "d2",
    "d5",
)
PETROL_MARKERS = (
    "benzin",
    "benzinas",
    "petrol",
    "gasoline",
    "бенз",
    "бензин",
    "tsi",
    "tfsi",
    "mpi",
    "gdi",
    "ecoboost",
)

VOLUME_PARAM_KEYS = (
    "Variklis",
    "Двигатель",
    "Darbinis tūris",
    "Darbinis tūris, cm³",
    "Рабочий объем",
    "Рабочий объём, см³",
    "Объём двигателя, см³",
)
VOLUME_PARAM_KEY_MARKERS = (
    "variklis",
    "двигатель",
    "engine",
    "tūris",
    "turis",
    "объем",
    "объём",
    "volume",
    "displacement",
)


def _format_liters(value: float) -> str:
    return f"{round(value, 1):.1f} L"


def parse_manual_volume_input(raw: str | None) -> float | None:
    """Parse liters or cm³ entered manually (e.g. 1.6, 1,6, 1600)."""
    text = (raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    liters = value / 1000 if value >= 100 else value
    if not (0.5 <= liters <= 10.0):
        return None
    return round(liters, 1)


def engine_volume_storage_text(liters: float) -> str:
    """Value stored in listings.engine so volume parsers pick it up."""
    if abs(liters - round(liters)) < 0.05:
        return f"{int(round(liters))} l"
    return f"{liters:.1f} l"


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
    stored = item.get("engine_liters")
    if stored is not None:
        try:
            liters = float(stored)
        except (TypeError, ValueError):
            liters = None
        else:
            if 0.5 <= liters <= 10.0:
                return round(liters, 1)
    cm3 = engine_volume_cm3(item)
    if cm3 is None:
        return None
    return cm3 / 1000


def _is_volume_param_key(key: str) -> bool:
    folded = key.casefold()
    return any(marker in folded for marker in VOLUME_PARAM_KEY_MARKERS)


def _iter_volume_param_values(params: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for param_key in VOLUME_PARAM_KEYS:
        value = params.get(param_key)
        if not value:
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    for param_key, value in params.items():
        if not value or param_key in VOLUME_PARAM_KEYS:
            continue
        if not _is_volume_param_key(str(param_key)):
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    return values


def engine_volume_cm3(item: dict[str, Any]) -> int | None:
    """Exact engine displacement in cm³ when parseable."""
    for key in ("description_ru", "description", "engine", "title"):
        value = item.get(key)
        if not value:
            continue
        cm3 = _parse_volume_cm3_from_text(str(value))
        if cm3 is not None:
            return cm3

    for value in _iter_volume_param_values(item.get("parameters") or {}):
        cm3 = _parse_volume_cm3_from_text(value)
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


def _listing_fuel_text(item: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("fuel", "engine", "title", "description_ru", "description"):
        value = item.get(key)
        if value:
            chunks.append(str(value).casefold())
    params = item.get("parameters") or {}
    for key in ("Kuro tipas", "Тип топлива", "Variklis", "Двигатель"):
        value = params.get(key)
        if value:
            chunks.append(str(value).casefold())
    return " ".join(chunks)


def _normalized_make_key(make: str) -> str:
    folded = make.casefold().strip()
    if folded.startswith("mercedes"):
        return "mercedes"
    return folded


def _is_diesel_listing(item: dict[str, Any]) -> bool:
    text = _listing_fuel_text(item)
    return any(marker in text for marker in DIESEL_MARKERS)


def _is_petrol_listing(item: dict[str, Any]) -> bool:
    if _is_diesel_listing(item):
        return False
    text = _listing_fuel_text(item)
    return any(marker in text for marker in PETROL_MARKERS)


def _is_nominal_16l_engine(*, cm3: int | None, liters: float | None) -> bool:
    if cm3 == 1600:
        return True
    if liters is not None and 1.55 <= liters <= 1.65:
        return True
    return False


def _customs_nominal_16_diesel_override_applies(item: dict[str, Any], cm3: int) -> bool:
    make, _model = listing_make_model(item)
    if make == "—" or _normalized_make_key(make) not in CUSTOMS_NOMINAL_16_DIESEL_MAKES:
        return False
    if not _is_diesel_listing(item):
        return False
    liters = cm3 / 1000
    return _is_nominal_16l_engine(cm3=cm3, liters=liters)


def _is_nominal_13l_engine(*, cm3: int | None, liters: float | None) -> bool:
    if cm3 == 1300:
        return True
    if liters is not None and 1.25 <= liters <= 1.35:
        return True
    return False


def _customs_nominal_13_petrol_override_applies(item: dict[str, Any], cm3: int) -> bool:
    make, _model = listing_make_model(item)
    if make == "—" or _normalized_make_key(make) not in CUSTOMS_NOMINAL_13_PETROL_MAKES:
        return False
    if not _is_petrol_listing(item):
        return False
    liters = cm3 / 1000
    return _is_nominal_13l_engine(cm3=cm3, liters=liters)


def customs_engine_volume_cm3(item: dict[str, Any]) -> int | None:
    """Engine displacement used for Belarus customs duty (may differ from display volume)."""
    from autoplius.engine_catalog import lookup_catalog_cm3

    catalog_cm3 = lookup_catalog_cm3(item)
    if catalog_cm3 is not None:
        return catalog_cm3

    cm3 = engine_volume_cm3(item)
    if cm3 is None:
        return None
    if _customs_nominal_16_diesel_override_applies(item, cm3):
        return CUSTOMS_NOMINAL_16_DIESEL_CM3
    if _customs_nominal_13_petrol_override_applies(item, cm3):
        return CUSTOMS_NOMINAL_13_PETROL_CM3
    return cm3
