"""Tab count injection should stay cheap on public pages."""

from __future__ import annotations

from pathlib import Path

import ui.app as app_module
from scraper.db import init_db
from ui.app import app


def test_public_tab_counts_skip_admin_queries(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite"
    init_db(db)
    monkeypatch.setitem(app.config, "DB_PATH", db)
    app_module._tab_counts_cache.clear()

    calls: list[str] = []

    def fake_count(path, filters):
        calls.append("count")
        return 7

    def boom_missing(path):
        calls.append("missing")
        raise AssertionError("admin catalog missing count should not run")

    def boom_new(path):
        calls.append("new")
        raise AssertionError("admin catalog new count should not run")

    monkeypatch.setattr(app_module, "count_listings", fake_count)
    monkeypatch.setattr(app_module, "engine_catalog_missing_count", boom_missing)
    monkeypatch.setattr(app_module, "engine_catalog_new_count", boom_new)

    with app.test_request_context("/calculator"):
        counts = app_module._tab_counts_for_request(db, admin=False)

    assert counts == {"electric_count": 7}
    assert calls == ["count"]

    # Cached: second call must not hit SQL again.
    with app.test_request_context("/calculator"):
        again = app_module._tab_counts_for_request(db, admin=False)
    assert again == counts
    assert calls == ["count"]


def test_admin_tab_counts_include_all(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.sqlite"
    init_db(db)
    monkeypatch.setitem(app.config, "DB_PATH", db)
    app_module._tab_counts_cache.clear()

    monkeypatch.setattr(app_module, "count_listings", lambda path, filters: 3)
    monkeypatch.setattr(app_module, "engine_catalog_missing_count", lambda path: 1)
    monkeypatch.setattr(app_module, "engine_catalog_new_count", lambda path: 2)

    with app.test_request_context("/"):
        counts = app_module._tab_counts_for_request(db, admin=True)

    assert counts["electric_count"] == 3
    assert counts["no_volume_count"] == 3
    assert counts["catalog_missing_count"] == 1
    assert counts["catalog_new_count"] == 2


def test_prewarm_includes_light_pages(monkeypatch):
    monkeypatch.delenv("UI_PREWARM_PATHS", raising=False)
    from ui.prewarm import DEFAULT_HOME_PATHS, home_paths

    paths = home_paths()
    assert paths == DEFAULT_HOME_PATHS
    assert "/calculator" in paths
    assert "/instruction" in paths
    assert "/privacy" in paths
    assert "/vin-check" in paths
