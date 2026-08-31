from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup

MYFIN_EURUSD_URL = "https://myfin.by/currency/eurusd"
_CACHE: dict[str, Any] = {"fetched_at": None, "eur_usd": None}
_CACHE_TTL = timedelta(minutes=30)
_FALLBACK_RATE = 1.158
_USER_AGENT = "Mozilla/5.0 (compatible; autoplius-scraper/1.0)"


def _fetch_myfin_html() -> str:
    request = urllib.request.Request(
        MYFIN_EURUSD_URL,
        headers={"User-Agent": _USER_AGENT},
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
        raise ValueError("myfin EUR/USD rate row not found")

    values = [
        span.get_text(strip=True).replace(",", ".")
        for span in row.select(".course-brief-info__b .accent")
    ]
    if len(values) < 2:
        raise ValueError("myfin buy rate not found")

    rate = float(values[1])
    if rate <= 0 or rate > 10:
        raise ValueError("myfin buy rate out of range")
    return rate


def _fetch_myfin_best_buy_rate() -> float:
    html = _fetch_myfin_html()
    rate = _parse_best_buy_rate(html)
    # Fallback regex if markup shifts slightly.
    if rate <= 0:
        match = re.search(
            r"course-brief-info--best-courses.*?course-brief-info__b.*?accent\">([\d.]+)</span>"
            r".*?course-brief-info__b.*?accent\">([\d.]+)</span>",
            html,
            re.S,
        )
        if match:
            rate = float(match.group(2))
    return rate


def eur_usd_rate() -> float:
    override = (os.environ.get("PRICE_RB_EUR_USD") or "").strip()
    if override:
        return float(override)

    now = datetime.now(timezone.utc)
    cached_at = _CACHE.get("fetched_at")
    cached_rate = _CACHE.get("eur_usd")
    if cached_at and cached_rate and now - cached_at < _CACHE_TTL:
        return cached_rate

    try:
        rate = _fetch_myfin_best_buy_rate()
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError):
        if cached_rate:
            return cached_rate
        rate = _FALLBACK_RATE

    _CACHE["fetched_at"] = now
    _CACHE["eur_usd"] = rate
    return rate


def estimate_price_rb_usd(price_eur: int | None, *, item: dict[str, Any] | None = None) -> int | None:
    if price_eur is None:
        return None
    factor = float(os.environ.get("PRICE_RB_LANDED_FACTOR", "1.0"))
    extra_usd = int(os.environ.get("PRICE_RB_EXTRA_USD", "0"))
    return int(round(price_eur * eur_usd_rate() * factor + extra_usd))
