from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.db import (
    default_db_path,
    get_latest_exchange_rate,
    save_exchange_rates,
)

_CACHE: dict[str, dict[str, object]] = {}
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


def _db_path() -> Path:
    raw = os.environ.get("DB_PATH", "").strip()
    if raw:
        return Path(raw)
    return default_db_path(_data_dir())


def _parse_rate_text(text: str) -> float:
    match = _RATE_NUMBER_RE.search((text or "").replace(",", "."))
    if not match:
        raise ValueError(f"myfin buy rate not found in {text!r}")
    rate = float(match.group(1))
    if rate <= 0:
        raise ValueError("myfin buy rate out of range")
    return rate


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


def fetch_myfin_pairs(*, force: bool = False) -> dict[str, float]:
    """Fetch current myfin rates without touching the database."""
    refreshed: dict[str, float] = {}
    for pair in MYFIN_URLS:
        rate = _parse_best_buy_rate(_fetch_html(MYFIN_URLS[pair]))
        refreshed[pair] = rate
    if force and len(refreshed) != len(MYFIN_URLS):
        raise RuntimeError("failed to refresh all myfin pairs")
    return refreshed


def refresh_myfin_rates(
    db_path: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, float]:
    """Fetch current myfin rates and append them to exchange_rates."""
    path = db_path or _db_path()
    pairs = fetch_myfin_pairs(force=force)
    save_exchange_rates(path, pairs)
    _load_cache_from_db(path, force=True)
    return pairs


def apply_exchange_rates(
    pairs: dict[str, float],
    db_path: Path | None = None,
    *,
    fetched_at: str | None = None,
) -> str:
    path = db_path or _db_path()
    when = save_exchange_rates(path, pairs, fetched_at=fetched_at)
    _load_cache_from_db(path, force=True)
    return when


def _load_cache_from_db(db_path: Path, *, force: bool = False) -> None:
    if not force:
        return
    _CACHE.clear()
    for pair in MYFIN_URLS:
        rate = get_latest_exchange_rate(db_path, pair)
        if rate is not None:
            _CACHE[pair] = {"fetched_at": datetime.now(timezone.utc), "rate": rate}


def myfin_best_buy_rate(pair: str, *, db_path: Path | None = None) -> float:
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

    path = db_path or _db_path()
    now = datetime.now(timezone.utc)
    cached = _CACHE.get(pair) or {}
    cached_at = cached.get("fetched_at")
    cached_rate = cached.get("rate")
    if (
        isinstance(cached_at, datetime)
        and cached_rate is not None
        and now - cached_at < _CACHE_TTL
    ):
        return float(cached_rate)

    db_rate = get_latest_exchange_rate(path, pair)
    if db_rate is not None:
        _CACHE[pair] = {"fetched_at": now, "rate": db_rate}
        return db_rate

    if cached_rate is not None:
        return float(cached_rate)
    return _FALLBACK[pair]


def eur_usd_rate(*, db_path: Path | None = None) -> float:
    return myfin_best_buy_rate("eurusd", db_path=db_path)


def usd_byn_rate(*, db_path: Path | None = None) -> float:
    """BYN per 1 USD at the best buy rate."""
    return myfin_best_buy_rate("usd", db_path=db_path)
