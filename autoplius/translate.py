from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

logger = logging.getLogger(__name__)

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LAST_CALL_AT = 0.0
_MAX_ATTEMPTS = 3
_PER_CALL_TIMEOUT_SEC = 25.0
_CHUNK_SIZE = 1200
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


def split_translation_chunks(text: str, *, max_len: int = _CHUNK_SIZE) -> list[str]:
    """Split long seller text into translator-friendly chunks."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    if len(cleaned) <= max_len:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        piece = remaining[:max_len]
        cut = max(piece.rfind(". "), piece.rfind("! "), piece.rfind("? "), piece.rfind("; "))
        if cut < max_len // 3:
            cut = piece.rfind(" ")
        if cut < max_len // 4:
            cut = max_len
        else:
            cut = cut + 1
        chunk = remaining[:cut].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip()
    return chunks


def _translate_chunks(
    text: str,
    translate_one: Callable[[str], str | None],
    *,
    pause_sec: float = 0.35,
) -> str | None:
    parts: list[str] = []
    for index, chunk in enumerate(split_translation_chunks(text)):
        if index and pause_sec > 0:
            time.sleep(pause_sec)
        translated = translate_one(chunk)
        cleaned = sanitize_translation(translated)
        if not cleaned:
            return None
        parts.append(cleaned)
    return sanitize_translation(" ".join(parts))


def _http_get_json(url: str, *, timeout: float = 15.0) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, *, timeout: float = 15.0) -> object:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _google_gtx_one(text: str, *, source: str) -> str | None:
    params = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": source,
            "tl": "ru",
            "dt": "t",
            "q": text,
        }
    )
    payload = _http_get_json(
        f"https://translate.googleapis.com/translate_a/single?{params}"
    )
    parts: list[str] = []
    for row in (payload[0] or []):
        if row and row[0]:
            parts.append(str(row[0]))
    return sanitize_translation("".join(parts))


def _google_gtx_translate(text: str, *, source: str) -> str | None:
    return _translate_chunks(
        text,
        lambda chunk: _google_gtx_one(chunk, source=source),
        pause_sec=0.45,
    )


def _mymemory_http_one(text: str) -> str | None:
    params = urllib.parse.urlencode({"q": text, "langpair": "lt|ru"})
    payload = _http_get_json(f"https://api.mymemory.translated.net/get?{params}")
    if not isinstance(payload, dict):
        return None
    response_data = payload.get("responseData") or {}
    translated = response_data.get("translatedText")
    return sanitize_translation(translated if isinstance(translated, str) else None)


def _mymemory_http_translate(text: str) -> str | None:
    return _translate_chunks(text, _mymemory_http_one, pause_sec=0.4)


def _libre_one(text: str) -> str | None:
    payload = _http_post_json(
        "https://libretranslate.com/translate",
        {"q": text, "source": "lt", "target": "ru", "format": "text"},
    )
    if not isinstance(payload, dict):
        return None
    translated = payload.get("translatedText")
    return sanitize_translation(translated if isinstance(translated, str) else None)


def _libre_translate(text: str) -> str | None:
    return _translate_chunks(text, _libre_one, pause_sec=0.5)


def _google_deep_one(text: str, *, source: str) -> str | None:
    from deep_translator import GoogleTranslator

    translated = GoogleTranslator(source=source, target="ru").translate(text)
    return sanitize_translation(translated)


def _google_deep_translate(text: str, *, source: str) -> str | None:
    return _translate_chunks(
        text,
        lambda chunk: _google_deep_one(chunk, source=source),
        pause_sec=0.4,
    )


def _backends() -> list[tuple[str, Callable[[str], str | None]]]:
    return [
        ("gtx-lt", lambda text: _google_gtx_translate(text, source="lt")),
        ("gtx-auto", lambda text: _google_gtx_translate(text, source="auto")),
        ("mymemory-http", _mymemory_http_translate),
        ("libre-lt", _libre_translate),
        ("google-lt", lambda text: _google_deep_translate(text, source="lt")),
        ("google-auto", lambda text: _google_deep_translate(text, source="auto")),
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
    payload = cleaned[:8000]
    rate_limited = False
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _LAST_CALL_AT
        wait = min_delay_sec * attempt
        if rate_limited:
            wait = max(wait, 3.0 * attempt)
        if elapsed < wait:
            time.sleep(wait - elapsed)

        for backend_name, backend in _backends():
            try:
                translated = _run_with_timeout(
                    lambda backend=backend: backend(payload),
                    _PER_CALL_TIMEOUT_SEC,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    rate_limited = True
                logger.warning(
                    "Description translation failed via %s (attempt %s/%s): %s",
                    backend_name,
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )
                translated = None
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
                if backend_name != "gtx-lt":
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
