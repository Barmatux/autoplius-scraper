"""Detect real seller text vs scraped specs/meta noise."""

from __future__ import annotations

import re
from typing import Any

from autoplius.translate import is_translation_error

_PARAM_LINE_RE = re.compile(r"^[^:：]{1,48}[:：]\s*.+", re.M)
_LISTING_META_PREFIXES = (
    "parduodamas",
    "parduodama",
    "naudotas",
    "продаётся",
    "продается",
)
_SPEC_FIELD_MARKERS = (
    "первая регистрация",
    "пробег",
    "тип топлива",
    "тип кузова",
    "коробка передач",
    "количество дверей",
    "выброс co",
    "vin-код",
    "pirma registracija",
    "rida",
    "kuro tipas",
    "kėbulo tipas",
    "pavarų d",
)


def _spec_field_hits(text: str) -> int:
    lowered = text.casefold()
    return sum(1 for marker in _SPEC_FIELD_MARKERS if marker in lowered)


def is_seller_description(text: str | None) -> bool:
    if not text:
        return False
    clean = text.strip()
    if len(clean) < 25:
        return False
    lowered = clean.casefold()
    if any(lowered.startswith(prefix) for prefix in _LISTING_META_PREFIXES):
        return False

    spec_hits = _spec_field_hits(clean)
    if spec_hits >= 3:
        return False
    if "регистрация" in lowered and "пробег" in lowered and clean.count(",") >= 3:
        return False

    lines = [line.strip() for line in re.split(r"[\n\r]+", clean) if line.strip()]
    if len(lines) >= 2:
        param_like = sum(1 for line in lines if _PARAM_LINE_RE.match(line))
        if param_like >= 2 and param_like / len(lines) >= 0.5:
            return False

    if len(lines) == 1 and clean.count(",") >= 4:
        if spec_hits >= 2 or len(clean) < 320:
            return False

    return True


def seller_description(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (primary_text, original_text) when text looks like a seller description."""
    original = item.get("description")
    translated = item.get("description_ru")
    if is_translation_error(translated):
        translated = None
    if translated and is_seller_description(translated):
        show_original = original if original and original != translated and is_seller_description(original) else None
        return translated, show_original
    if is_seller_description(original):
        return original, None
    return None, None
