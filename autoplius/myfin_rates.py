from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

_CACHE: dict[str, Any] = {}
_FILE_CACHE: dict[str, Any] | None = None
_FILE_CACHE_MTIME: float | None = None
_CACHE_TTL = timedelta(minutes=30)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MYFIN_URLS = {
    "eurusd": "https://myfin.by/currency/eurusd",
    "usd": "https://myfin.by/currency/usd",
}
_FALLBACK = {
    "eurusd": 1.158,
    "usd": 3.04,
}
_RATE_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def _data_dir() -> Path:
    raw = os.environ.get("DATA_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[1] / "data"


def _cache_file_path() -> Path:
    return _data_dir() / "myfin_rates.json"


def _parse_rate_text(text: str) -> float:
    match = _RATE_NUMBER_RE.search((text or "").replace(",", "."))
    if not match:
        raise ValueError(f"myfin buy rate not found in {text!r}")
    rate = float(match.group(1))
    if rate <= 0:
        raise ValueError("myfin buy rate out of range")
    return rate


def _load_file_cache(*, force: bool = False) -> dict[str, Any]:
    global _FILE_CACHE, _FILE_CACHE_MTIME
    path = _cache_file_path()
    if not path.is_file():
        _FILE_CACHE = {}
        _FILE_CACHE_MTIME = None
        return {}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _FILE_CACHE or {}
    if not force and _FILE_CACHE is not None and _FILE_CACHE_MTIME == mtime:
        return _FILE_CACHE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        _FILE_CACHE = {}
        _FILE_CACHE_MTIME = mtime
        return {}
    pairs = payload.get("pairs")
    _FILE_CACHE = pairs if isinstance(pairs, dict) else {}
    _FILE_CACHE_MTIME = mtime
    return _FILE_CACHE


def _save_file_cache(pairs: dict[str, Any]) -> None:
    global _FILE_CACHE, _FILE_CACHE_MTIME
    path = _cache_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pairs": pairs,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    _FILE_CACHE = pairs
    try:
        _FILE_CACHE_MTIME = path.stat().st_mtime
    except OSError:
        _FILE_CACHE_MTIME = None


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_best_buy_rate(html: str) -> float:
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(".course-brief-info--best-courses")
    if block is None:
        raise ValueError("myfin best courses block not found")

    row = block.select_one(".course-brief-info__body .course-brief-info__r")
    if row is None:
        raise ValueError("myfin rate row not found")

    values = [span.get_text(strip=True) for span in row.select(".course-brief-info__b .accent")]
    if len(values) < 2:
        raise ValueError("myfin buy rate not found")

    return _parse_rate_text(values[1])


def refresh_myfin_rates(*, force: bool = False) -> dict[str, float]:
    """Fetch current myfin rates and persist them to disk."""
    now = datetime.now(timezone.utc)
    file_pairs = _load_file_cache()
    refreshed: dict[str, float] = {}

    for pair in MYFIN_URLS:
        try:
            rate = _parse_best_buy_rate(_fetch_html(MYFIN_URLS[pair]))
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError) as exc:
            if force:
                raise RuntimeError(f"failed to refresh {pair}: {exc}") from exc
            cached_rate = (file_pairs.get(pair) or {}).get("rate")
            if cached_rate is not None:
                refreshed[pair] = float(cached_rate)
            else:
                refreshed[pair] = _FALLBACK[pair]
            continue

        file_pairs[pair] = {"fetched_at": now.isoformat(), "rate": rate}
        _CACHE[pair] = {"fetched_at": now, "rate": rate}
        refreshed[pair] = rate

    if any(pair in file_pairs for pair in MYFIN_URLS):
        _save_file_cache(file_pairs)
    return refreshed


def myfin_best_buy_rate(pair: str) -> float:
    """Best «Купить» rate from myfin.by (eurusd cross or USD/BYN)."""
    if pair not in MYFIN_URLS:
        raise ValueError(f"unsupported myfin pair: {pair}")

    env_key = {
        "eurusd": "PRICE_RB_EUR_USD",
        "usd": "PRICE_RB_USD_BYN",
    }[pair]
    override = (os.environ.get(env_key) or "").strip()
    if override:
        return float(override)

    now = datetime.now(timezone.utc)
    cached = _CACHE.get(pair) or {}
    cached_at = cached.get("fetched_at")
    cached_rate = cached.get("rate")
    if cached_at and cached_rate and now - cached_at < _CACHE_TTL:
        return float(cached_rate)

    file_entry = _load_file_cache().get(pair) or {}
    file_rate = file_entry.get("rate")
    if file_rate is not None:
        rate = float(file_rate)
        fetched_at = now
        file_fetched_at = file_entry.get("fetched_at")
        if file_fetched_at:
            try:
                fetched_at = datetime.fromisoformat(str(file_fetched_at).replace("Z", "+00:00"))
            except ValueError:
                fetched_at = now
        _CACHE[pair] = {"fetched_at": fetched_at, "rate": rate}
        return rate

    try:
        rate = _parse_best_buy_rate(_fetch_html(MYFIN_URLS[pair]))
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError):
        if cached_rate is not None:
            return float(cached_rate)
        return _FALLBACK[pair]

    file_pairs = _load_file_cache(force=True)
    file_pairs[pair] = {"fetched_at": now.isoformat(), "rate": rate}
    _save_file_cache(file_pairs)
    _load_file_cache(force=True)
    _CACHE[pair] = {"fetched_at": now, "rate": rate}
    return rate


def eur_usd_rate() -> float:
    return myfin_best_buy_rate("eurusd")


def usd_byn_rate() -> float:
    """BYN per 1 USD at the best buy rate."""
    return myfin_best_buy_rate("usd")
