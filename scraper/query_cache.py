"""Short-lived in-process cache for expensive UI SQLite aggregations."""

from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeVar

from scraper.listing_sql_filters import ListingFilters

T = TypeVar("T")

_DEFAULT_TTL_SEC = 180
_MAX_FILTER_ENTRIES = 64

_filter_cache: dict[str, tuple[float, Any]] = {}
_stats_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _ttl_sec() -> float:
    raw = os.environ.get("UI_QUERY_CACHE_TTL_SEC", "").strip()
    if raw.isdigit():
        return float(max(0, int(raw)))
    return float(_DEFAULT_TTL_SEC)


def invalidate_query_cache() -> None:
    _filter_cache.clear()
    _stats_cache.clear()


def _db_cache_token(db_path: Path) -> str:
    try:
        stat = db_path.resolve().stat()
    except OSError:
        return str(db_path.resolve())
    return f"{db_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def _filters_cache_key(db_path: Path, filters: ListingFilters) -> str:
    return f"{_db_cache_token(db_path)}:{json.dumps(asdict(filters), sort_keys=True, ensure_ascii=True)}"


def _get_cached(cache: dict[str, tuple[float, T]], key: str) -> T | None:
    ttl = _ttl_sec()
    if ttl <= 0:
        return None
    entry = cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.monotonic() >= expires_at:
        cache.pop(key, None)
        return None
    return copy.deepcopy(value)


def _set_cached(cache: dict[str, tuple[float, T]], key: str, value: T) -> None:
    ttl = _ttl_sec()
    if ttl <= 0:
        return
    cache[key] = (time.monotonic() + ttl, copy.deepcopy(value))


def _trim_filter_cache() -> None:
    if len(_filter_cache) <= _MAX_FILTER_ENTRIES:
        return
    now = time.monotonic()
    expired = [key for key, (expires_at, _) in _filter_cache.items() if expires_at <= now]
    for key in expired:
        _filter_cache.pop(key, None)
    while len(_filter_cache) > _MAX_FILTER_ENTRIES:
        oldest_key = min(_filter_cache, key=lambda key: _filter_cache[key][0])
        _filter_cache.pop(oldest_key, None)


def cached_db_stats(db_path: Path, loader: Any) -> dict[str, Any]:
    key = _db_cache_token(db_path)
    cached = _get_cached(_stats_cache, key)
    if cached is not None:
        return cached
    stats = loader(db_path)
    _set_cached(_stats_cache, key, stats)
    return stats


def cached_listing_filter_options(
    db_path: Path,
    filters: ListingFilters,
    loader: Any,
) -> Any:
    key = _filters_cache_key(db_path, filters)
    cached = _get_cached(_filter_cache, key)
    if cached is not None:
        return cached
    options = loader(db_path, filters)
    _set_cached(_filter_cache, key, options)
    _trim_filter_cache()
    return options
