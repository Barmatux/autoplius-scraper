from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup

_CACHE: dict[str, Any] = {}
_CACHE_TTL = timedelta(minutes=30)
_USER_AGENT = "Mozilla/5.0 (compatible; autoplius-scraper/1.0)"

MYFIN_URLS = {
    "eurusd": "https://myfin.by/currency/eurusd",
    "usd": "https://myfin.by/currency/usd",
}
_FALLBACK = {
    "eurusd": 1.158,
    "usd": 3.04,
}


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
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

    values = [
        span.get_text(strip=True).replace(",", ".")
        for span in row.select(".course-brief-info__b .accent")
    ]
    if len(values) < 2:
        raise ValueError("myfin buy rate not found")

    rate = float(values[1])
    if rate <= 0:
        raise ValueError("myfin buy rate out of range")
    return rate


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
        return cached_rate

    try:
        rate = _parse_best_buy_rate(_fetch_html(MYFIN_URLS[pair]))
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError):
        if cached_rate:
            return cached_rate
        # Regex fallback on last successful HTML is unavailable; use constant.
        rate = _FALLBACK[pair]

    _CACHE[pair] = {"fetched_at": now, "rate": rate}
    return rate


def eur_usd_rate() -> float:
    return myfin_best_buy_rate("eurusd")


def usd_byn_rate() -> float:
    """BYN per 1 USD at the best buy rate."""
    return myfin_best_buy_rate("usd")
