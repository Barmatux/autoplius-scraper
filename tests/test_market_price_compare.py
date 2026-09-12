"""Market average price comparison helpers."""

from __future__ import annotations

from autoplius.market_price_compare import (
    MarketPriceCompare,
    _pick_best_item,
    compare_listing_to_market,
    lookup_market_avg,
)
from scraper.auto160_market_client import Auto160MarketClient


def test_pick_best_item_prefers_60_day_window():
    picked = _pick_best_item(
        [
            {"window_days": 30, "sample_count": 20, "avg_price_byn": "10000"},
            {"window_days": 90, "sample_count": 12, "avg_price_byn": "12000"},
            {"window_days": 60, "sample_count": 8, "avg_price_byn": "11000"},
        ]
    )
    assert picked is not None
    assert picked["window_days"] == 60


def test_pick_best_item_falls_back_to_90_without_60():
    picked = _pick_best_item(
        [
            {"window_days": 30, "sample_count": 20, "avg_price_byn": "10000"},
            {"window_days": 90, "sample_count": 12, "avg_price_byn": "12000"},
        ]
    )
    assert picked is not None
    assert picked["window_days"] == 90


def test_compare_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("MARKET_PRICES_API_KEY", raising=False)
    assert compare_listing_to_market({"title": "BMW X1, 2015", "price_eur": 10000}) is None


def test_compare_listing_to_market(monkeypatch):
    monkeypatch.setenv("MARKET_PRICES_API_KEY", "test-key")
    monkeypatch.setenv("AUTO160_MARKET_BASE_URL", "https://example.test/api/v1/market")

    def fake_lookup(self, **kwargs):
        return [
            {
                "brand": "BMW",
                "model": "X1",
                "year": 2015,
                "window_days": 90,
                "avg_price_byn": "20000.00",
                "sample_count": 14,
            }
        ]

    monkeypatch.setattr(Auto160MarketClient, "lookup_avg_price", fake_lookup)
    monkeypatch.setattr(
        "autoplius.market_price_compare.estimate_price_rb",
        lambda item: type(
            "B",
            (),
            {"total_usd": 5000, "usd_byn": 3.2},
        )(),
    )
    monkeypatch.setattr(
        "autoplius.market_price_compare.listing_make_model",
        lambda item: ("BMW", "X1"),
    )
    monkeypatch.setattr(
        "autoplius.market_price_compare.listing_year",
        lambda item: 2015,
    )
    # Clear module cache between runs.
    import autoplius.market_price_compare as mpc

    mpc._cache.clear()

    result = compare_listing_to_market({"title": "BMW X1"})
    assert isinstance(result, MarketPriceCompare)
    assert result.avg_price_byn == 20000.0
    assert result.listing_price_byn == 16000.0  # 5000 * 3.2
    assert result.cheaper is True
    tpl = result.as_template_dict()
    assert "ниже рынка" in tpl["label"]


def test_lookup_caches_none(monkeypatch):
    monkeypatch.setenv("MARKET_PRICES_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_lookup(self, **kwargs):
        calls["n"] += 1
        return []

    monkeypatch.setattr(Auto160MarketClient, "lookup_avg_price", fake_lookup)
    import autoplius.market_price_compare as mpc

    mpc._cache.clear()
    assert lookup_market_avg(brand="Audi", model="A4", year=2014) is None
    assert lookup_market_avg(brand="Audi", model="A4", year=2014) is None
    # First call tries several windows + all-windows; second should be cached.
    assert calls["n"] >= 1
    first_calls = calls["n"]
    assert lookup_market_avg(brand="Audi", model="A4", year=2014) is None
    assert calls["n"] == first_calls
