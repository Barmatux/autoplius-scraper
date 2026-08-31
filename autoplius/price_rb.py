from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

_CACHE: dict[str, Any] = {"fetched_at": None, "eur_usd": None}
_CACHE_TTL = timedelta(hours=1)
_NBRB_EUR_URL = "https://api.nbrb.by/exrates/rates/EUR?parammode=2"
_NBRB_USD_URL = "https://api.nbrb.by/exrates/rates/USD?parammode=2"


def _fetch_nbrb_rate(url: str) -> tuple[float, int]:
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)
    return float(payload["Cur_OfficialRate"]), int(payload.get("Cur_Scale") or 1)


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
        eur_rate, eur_scale = _fetch_nbrb_rate(_NBRB_EUR_URL)
        usd_rate, usd_scale = _fetch_nbrb_rate(_NBRB_USD_URL)
        if eur_rate <= 0 or usd_rate <= 0:
            raise ValueError("invalid NBRB rate")
        # BYN per 1 EUR / BYN per 1 USD
        rate = (eur_rate / eur_scale) / (usd_rate / usd_scale)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError):
        rate = 1.08

    _CACHE["fetched_at"] = now
    _CACHE["eur_usd"] = rate
    return rate


def estimate_price_rb_usd(price_eur: int | None, *, item: dict[str, Any] | None = None) -> int | None:
    if price_eur is None:
        return None
    factor = float(os.environ.get("PRICE_RB_LANDED_FACTOR", "1.0"))
    extra_usd = int(os.environ.get("PRICE_RB_EXTRA_USD", "0"))
    return int(round(price_eur * eur_usd_rate() * factor + extra_usd))
