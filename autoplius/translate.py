from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger(__name__)

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LAST_CALL_AT = 0.0


def cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if _CYRILLIC_RE.match(ch))
    return cyr / len(letters)


def looks_russian(text: str, *, threshold: float = 0.45) -> bool:
    return cyrillic_ratio(text) >= threshold


def translate_to_russian(
    text: str | None,
    *,
    enabled: bool = True,
    min_delay_sec: float = 0.15,
) -> str | None:
    if not enabled:
        return None
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) < 3:
        return cleaned

    if looks_russian(cleaned):
        return cleaned

    global _LAST_CALL_AT
    elapsed = time.monotonic() - _LAST_CALL_AT
    if elapsed < min_delay_sec:
        time.sleep(min_delay_sec - elapsed)

    try:
        from deep_translator import GoogleTranslator

        translated = GoogleTranslator(source="auto", target="ru").translate(cleaned[:4500])
    except Exception as exc:
        logger.warning("Description translation failed: %s", exc)
        return None

    _LAST_CALL_AT = time.monotonic()
    if not translated:
        return None
    return re.sub(r"\s+", " ", translated.strip())
