from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

logger = logging.getLogger(__name__)

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LAST_CALL_AT = 0.0
_MAX_ATTEMPTS = 3
_PER_CALL_TIMEOUT_SEC = 8.0
_ERROR_MARKERS = (
    "error 500",
    "server error",
    "that's an error",
    "please try again later",
    "that's all we know",
    "too many requests",
    "query length limit",
    "invalid",
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


def is_usable_russian_text(text: str | None, *, threshold: float = 0.45) -> bool:
    if not text or is_translation_error(text):
        return False
    return looks_russian(text, threshold=threshold)


def _run_with_timeout(fn: Callable[[], str | None], timeout_sec: float) -> str | None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeout:
            future.cancel()
            logger.warning("Description translation timed out after %.1fs", timeout_sec)
            return None


def _google_translate(text: str, *, source: str) -> str | None:
    from deep_translator import GoogleTranslator

    translated = GoogleTranslator(source=source, target="ru").translate(text)
    return sanitize_translation(translated)


def _mymemory_translate(text: str) -> str | None:
    from deep_translator import MyMemoryTranslator

    # MyMemory free tier is picky about length; translate in chunks.
    chunks: list[str] = []
    remaining = text
    while remaining:
        piece = remaining[:450]
        cut = piece.rfind(" ")
        if cut >= 200:
            piece = piece[:cut]
        remaining = remaining[len(piece) :].lstrip()
        translated = MyMemoryTranslator(source="lt-LT", target="ru-RU").translate(piece)
        cleaned = sanitize_translation(translated)
        if not cleaned:
            return None
        chunks.append(cleaned)
    return sanitize_translation(" ".join(chunks))


def _backends() -> list[tuple[str, Callable[[str], str | None]]]:
    return [
        ("google-lt", lambda text: _google_translate(text, source="lt")),
        ("google-auto", lambda text: _google_translate(text, source="auto")),
        ("mymemory-lt", _mymemory_translate),
    ]


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
    payload = cleaned[:4500]
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _LAST_CALL_AT
        wait = min_delay_sec * attempt
        if elapsed < wait:
            time.sleep(wait - elapsed)

        for backend_name, backend in _backends():
            try:
                translated = _run_with_timeout(
                    lambda backend=backend: backend(payload),
                    _PER_CALL_TIMEOUT_SEC,
                )
            except Exception as exc:
                logger.warning(
                    "Description translation failed via %s (attempt %s/%s): %s",
                    backend_name,
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )
                translated = None
            finally:
                _LAST_CALL_AT = time.monotonic()

            if translated and looks_russian(translated):
                if backend_name != "google-lt":
                    logger.info("Description translated via %s", backend_name)
                return translated
            if translated and not looks_russian(translated):
                logger.warning(
                    "Description translation via %s attempt %s/%s did not look Russian",
                    backend_name,
                    attempt,
                    _MAX_ATTEMPTS,
                )

        if attempt < _MAX_ATTEMPTS:
            time.sleep(wait)

    return None
