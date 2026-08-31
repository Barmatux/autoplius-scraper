from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger(__name__)

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LAST_CALL_AT = 0.0
_MAX_ATTEMPTS = 4
_ERROR_MARKERS = (
    "error 500",
    "server error",
    "that's an error",
    "please try again later",
    "that's all we know",
    "too many requests",
)


def is_translation_error(text: str | None) -> bool:
    if not text:
        return False
    blob = re.sub(r"\s+", " ", text.strip()).lower()
    return any(marker in blob for marker in _ERROR_MARKERS)


def sanitize_translation(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text.strip())
    if is_translation_error(cleaned):
        return None
    return cleaned

def cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if _CYRILLIC_RE.match(ch))
    return cyr / len(letters)


def looks_russian(text: str, *, threshold: float = 0.45) -> bool:
    return cyrillic_ratio(text) >= threshold


def _call_translator(text: str) -> str | None:
    from deep_translator import GoogleTranslator

    translated = GoogleTranslator(source="auto", target="ru").translate(text)
    return sanitize_translation(translated)


def translate_to_russian(
    text: str | None,
    *,
    enabled: bool = True,
    min_delay_sec: float = 0.5,
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
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _LAST_CALL_AT
        wait = min_delay_sec * attempt
        if elapsed < wait:
            time.sleep(wait - elapsed)

        try:
            translated = _call_translator(cleaned[:4500])
        except Exception as exc:
            logger.warning("Description translation failed (attempt %s/%s): %s", attempt, _MAX_ATTEMPTS, exc)
            translated = None
        finally:
            _LAST_CALL_AT = time.monotonic()

        if translated:
            return translated

        if attempt < _MAX_ATTEMPTS:
            time.sleep(wait)

    return None
