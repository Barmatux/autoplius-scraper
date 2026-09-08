"""In-process HTML cache for anonymous list/detail pages (users + bots)."""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, str]] = {}

_DEFAULT_HOME_TTL = 90
_DEFAULT_HOME_BOT_TTL = 180
_DEFAULT_LISTING_BOT_TTL = 300
_MAX_ENTRIES = 512

_BOT_UA_RE = re.compile(
    r"(yandex|googlebot|bingbot|baiduspider|duckduckbot|slurp|"
    r"facebookexternalhit|semrush|ahrefs|mj12|dotbot|petalbot|"
    r"bytespider|gptbot|chatgpt-user|oai-searchbot|claudebot|anthropic|"
    r"amazonbot|applebot|twitterbot|ccbot|google-extended|"
    r"meta-externalagent|cohere-ai|perplexity)",
    re.I,
)

_AI_BOT_UA_RE = re.compile(
    r"(gptbot|chatgpt-user|oai-searchbot|claudebot|anthropic-ai|claude-web|"
    r"bytespider|ccbot|google-extended|meta-externalagent|meta-externalfetcher|"
    r"cohere-ai|perplexitybot|diffbot|img2dataset|amazonbot)",
    re.I,
)


def is_bot_user_agent(user_agent: str | None) -> bool:
    return bool(_BOT_UA_RE.search(user_agent or ""))


def is_ai_bot_user_agent(user_agent: str | None) -> bool:
    return bool(_AI_BOT_UA_RE.search(user_agent or ""))


def _env_ttl(name: str, default: int) -> float:
    raw = os.environ.get(name, "").strip()
    if raw.isdigit():
        return float(max(0, int(raw)))
    return float(default)


def home_cache_ttl(*, bot: bool) -> float:
    if bot:
        return _env_ttl("UI_HOME_CACHE_BOT_TTL_SEC", _DEFAULT_HOME_BOT_TTL)
    return _env_ttl("UI_HOME_CACHE_TTL_SEC", _DEFAULT_HOME_TTL)


def listing_bot_cache_ttl() -> float:
    return _env_ttl("UI_LISTING_CACHE_BOT_TTL_SEC", _DEFAULT_LISTING_BOT_TTL)


def invalidate_page_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _db_token(db_path: Path) -> str:
    try:
        stat = db_path.resolve().stat()
    except OSError:
        return str(db_path)
    return f"{db_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def make_cache_key(kind: str, db_path: Path, query: str) -> str:
    return f"{kind}|{_db_token(db_path)}|{query}"


def get_cached_html(key: str) -> str | None:
    now = time.monotonic()
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        expires_at, html = entry
        if now >= expires_at:
            _CACHE.pop(key, None)
            return None
        return html


def set_cached_html(key: str, html: str, ttl_sec: float) -> None:
    if ttl_sec <= 0 or not html:
        return
    expires_at = time.monotonic() + ttl_sec
    with _LOCK:
        _CACHE[key] = (expires_at, html)
        _trim_locked()


def _trim_locked() -> None:
    if len(_CACHE) <= _MAX_ENTRIES:
        return
    now = time.monotonic()
    expired = [key for key, (expires_at, _) in _CACHE.items() if expires_at <= now]
    for key in expired:
        _CACHE.pop(key, None)
    while len(_CACHE) > _MAX_ENTRIES:
        oldest = min(_CACHE, key=lambda item: _CACHE[item][0])
        _CACHE.pop(oldest, None)
