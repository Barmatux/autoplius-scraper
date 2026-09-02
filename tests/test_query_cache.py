from pathlib import Path
from unittest.mock import MagicMock

from scraper.db import db_stats
from scraper.listing_filter_options import ListingFilterOptions, fetch_listing_filter_options
from scraper.listing_sql_filters import ListingFilters
from scraper.query_cache import invalidate_query_cache


def test_db_stats_uses_cache(monkeypatch):
    invalidate_query_cache()
    calls = {"n": 0}

    def fake_load(db_path: Path):
        calls["n"] += 1
        return {"exists": True, "listings": calls["n"]}

    monkeypatch.setattr("scraper.db._load_db_stats", fake_load)

    path = Path("data/test.db")
    first = db_stats(path)
    second = db_stats(path)

    assert first == second == {"exists": True, "listings": 1}
    assert calls["n"] == 1


def test_filter_options_uses_cache(monkeypatch):
    invalidate_query_cache()
    calls = {"n": 0}
    filters = ListingFilters(q="bmw")

    def fake_load(db_path: Path, active_filters: ListingFilters):
        calls["n"] += 1
        assert active_filters == filters
        return ListingFilterOptions([], {"makes": [], "modelMap": {}, "makeCounts": {}}, [], [], [], [], [])

    monkeypatch.setattr(
        "scraper.listing_filter_options._load_listing_filter_options",
        fake_load,
    )

    path = Path("data/test.db")
    fetch_listing_filter_options(path, filters)
    fetch_listing_filter_options(path, filters)

    assert calls["n"] == 1


def test_filter_options_cache_key_changes_with_filters(monkeypatch):
    invalidate_query_cache()
    calls = {"n": 0}

    def fake_load(db_path: Path, active_filters: ListingFilters):
        calls["n"] += 1
        return ListingFilterOptions([], {"makes": [], "modelMap": {}, "makeCounts": {}}, [], [], [], [], [])

    monkeypatch.setattr(
        "scraper.listing_filter_options._load_listing_filter_options",
        fake_load,
    )

    path = Path("data/test.db")
    fetch_listing_filter_options(path, ListingFilters(q="bmw"))
    fetch_listing_filter_options(path, ListingFilters(q="audi"))

    assert calls["n"] == 2


def test_invalidate_query_cache_clears_entries(monkeypatch):
    invalidate_query_cache()
    loader = MagicMock(return_value={"exists": True, "listings": 1})
    monkeypatch.setattr("scraper.db._load_db_stats", loader)

    path = Path("data/test.db")
    db_stats(path)
    invalidate_query_cache()
    db_stats(path)

    assert loader.call_count == 2
