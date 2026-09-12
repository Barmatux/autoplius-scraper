"""Compare listing landed USD price to auto160 market average (when available)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from autoplius.catalog_filters import listing_year
from autoplius.listing_display import listing_make_model
from autoplius.price_rb import estimate_price_rb
from scraper.auto160_market_client import (
    Auto160MarketClient,
    Auto160MarketError,
    market_api_configured,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 3600.0
_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
# Prefer 60-day market avg; fall back to 90 then 30 when no samples.
_WINDOWS = (60, 90, 30)


def _fmt_money(amount: float, *, signed: bool = False) -> str:
    value = int(round(amount))
    text = f"{value:,}".replace(",", " ")
    if signed and value > 0:
        return f"+{text}"
    return text


@dataclass(frozen=True)
class MarketPriceCompare:
    brand: str
    model: str
    year: int
    window_days: int
    sample_count: int
    avg_price_usd: float
    avg_price_byn: float
    listing_price_usd: float
    listing_price_byn: float
    delta_usd: float
    delta_byn: float
    delta_pct: float

    @property
    def cheaper(self) -> bool:
        return self.delta_usd < 0

    def as_template_dict(self) -> dict[str, Any]:
        delta_i = int(round(self.delta_usd))
        return {
            "brand": self.brand,
            "model": self.model,
            "year": self.year,
            "window_days": self.window_days,
            "sample_count": self.sample_count,
            "avg_price_usd": int(round(self.avg_price_usd)),
            "avg_price_usd_fmt": _fmt_money(self.avg_price_usd),
            "avg_price_byn": int(round(self.avg_price_byn)),
            "avg_price_byn_fmt": _fmt_money(self.avg_price_byn),
            "listing_price_usd": int(round(self.listing_price_usd)),
            "listing_price_usd_fmt": _fmt_money(self.listing_price_usd),
            "listing_price_byn": int(round(self.listing_price_byn)),
            "listing_price_byn_fmt": _fmt_money(self.listing_price_byn),
            "delta_usd": delta_i,
            "delta_usd_fmt": _fmt_money(self.delta_usd, signed=True),
            "delta_byn": int(round(self.delta_byn)),
            "delta_byn_fmt": _fmt_money(self.delta_byn, signed=True),
            "delta_pct": round(self.delta_pct, 1),
            "delta_pct_fmt": f"{self.delta_pct:+.1f}%",
            "cheaper": self.cheaper,
            "label": (
                "ниже рынка"
                if self.cheaper
                else ("выше рынка" if delta_i > 0 else "около рынка")
            ),
        }


def _parse_money(value: Any) -> float | None:
    if value is None:
        return None
    try:
        amount = float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _cache_get(key: str) -> tuple[bool, dict[str, Any] | None]:
    entry = _cache.get(key)
    if entry is None:
        return False, None
    expires_at, value = entry
    if time.monotonic() >= expires_at:
        _cache.pop(key, None)
        return False, None
    return True, value


def _cache_set(key: str, value: dict[str, Any] | None) -> None:
    _cache[key] = (time.monotonic() + _CACHE_TTL_SEC, value)
    if len(_cache) > 512:
        oldest = min(_cache, key=lambda item: _cache[item][0])
        _cache.pop(oldest, None)


def _window_rank(window_days: int) -> int:
    try:
        return _WINDOWS.index(window_days)
    except ValueError:
        return len(_WINDOWS)


def _item_has_price(item: dict[str, Any]) -> bool:
    return (
        _parse_money(item.get("avg_price_usd")) is not None
        or _parse_money(item.get("avg_price_byn")) is not None
    )


def _pick_best_item(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for item in items:
        window = item.get("window_days")
        samples = item.get("sample_count")
        try:
            window_i = int(window) if window is not None else 0
            samples_i = int(samples) if samples is not None else 0
        except (TypeError, ValueError):
            continue
        if not _item_has_price(item):
            continue
        scored.append((window_i, samples_i, item))
    if not scored:
        return None
    # Prefer preferred window order (60 → 90 → 30), then more samples.
    scored.sort(key=lambda row: (_window_rank(row[0]), -row[1]))
    return scored[0][2]


def lookup_market_avg(
    *,
    brand: str,
    model: str,
    year: int,
) -> dict[str, Any] | None:
    if not market_api_configured():
        return None
    cache_key = f"{brand.casefold()}|{model.casefold()}|{year}"
    hit, cached = _cache_get(cache_key)
    if hit:
        return cached

    try:
        client = Auto160MarketClient()
    except ValueError:
        _cache_set(cache_key, None)
        return None

    found: dict[str, Any] | None = None
    try:
        for window in _WINDOWS:
            items = client.lookup_avg_price(
                brand=brand,
                model=model,
                year=year,
                window_days=window,
            )
            picked = _pick_best_item(items)
            if picked is not None:
                found = picked
                break
        if found is None:
            # All windows in one call (API returns matching windows).
            items = client.lookup_avg_price(
                brand=brand,
                model=model,
                year=year,
                window_days=None,
            )
            found = _pick_best_item(items)
    except Auto160MarketError as exc:
        logger.info("market lookup skipped: %s %s %s (%s)", brand, model, year, exc)
        found = None

    _cache_set(cache_key, found)
    return found


def compare_listing_to_market(item: dict[str, Any]) -> MarketPriceCompare | None:
    """Return market comparison for a listing, or None when not possible."""
    if not market_api_configured():
        return None

    make, model = listing_make_model(item)
    year = listing_year(item)
    if not make or make == "—" or not model or year is None:
        return None

    breakdown = estimate_price_rb(item)
    if breakdown is None or breakdown.usd_byn <= 0 or breakdown.total_usd <= 0:
        return None
    listing_usd = float(breakdown.total_usd)
    listing_byn = listing_usd * float(breakdown.usd_byn)

    avg_row = lookup_market_avg(brand=make, model=model, year=int(year))
    if not avg_row:
        return None

    avg_usd = _parse_money(avg_row.get("avg_price_usd"))
    avg_byn = _parse_money(avg_row.get("avg_price_byn"))
    if avg_usd is None and avg_byn is not None:
        avg_usd = avg_byn / float(breakdown.usd_byn)
    if avg_byn is None and avg_usd is not None:
        avg_byn = avg_usd * float(breakdown.usd_byn)
    if avg_usd is None or avg_byn is None:
        return None

    try:
        window_days = int(avg_row.get("window_days") or 0)
        sample_count = int(avg_row.get("sample_count") or 0)
    except (TypeError, ValueError):
        return None
    if window_days <= 0 or sample_count <= 0:
        return None

    delta_usd = listing_usd - avg_usd
    delta_byn = listing_byn - avg_byn
    delta_pct = (delta_usd / avg_usd) * 100.0 if avg_usd else 0.0
    return MarketPriceCompare(
        brand=make,
        model=model,
        year=int(year),
        window_days=window_days,
        sample_count=sample_count,
        avg_price_usd=avg_usd,
        avg_price_byn=avg_byn,
        listing_price_usd=listing_usd,
        listing_price_byn=listing_byn,
        delta_usd=delta_usd,
        delta_byn=delta_byn,
        delta_pct=delta_pct,
    )
