from __future__ import annotations

import pytest


def test_set_listing_engine_volume_updates_liters(tmp_path):
    from scraper.db import connect, fetch_listing, init_db, set_listing_engine_volume
    from scraper.listing_query import fetch_listing_ids
    from scraper.listing_sql_filters import ListingFilters

    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, title, year, price_eur, status, first_seen_at, last_seen_at, detail_scraped
            ) VALUES (501, 'Renault Clio, 2020', '2020-01', 10000, 'active', datetime('now'), datetime('now'), 0)
            """
        )

    assert fetch_listing_ids(
        db_path,
        ListingFilters(engine_volume_missing=True, catalog_filter=False),
    ) == [501]

    updated = set_listing_engine_volume(db_path, 501, 1.6)
    assert updated is not None
    item = fetch_listing(db_path, 501)
    assert item is not None
    assert item["engine_liters"] == 1.6
    assert item["engine"] == "1.6 l"
    assert "engine" in (item.get("manual_overrides") or set())
    assert not fetch_listing_ids(
        db_path,
        ListingFilters(engine_volume_missing=True, catalog_filter=False),
    )


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("flask") is None,
    reason="Flask is not installed",
)
def test_api_listing_engine_volume_requires_admin(tmp_path, monkeypatch):
    import ui.app as ui_app
    from scraper.db import connect, init_db

    db_path = tmp_path / "test.db"
    ui_app.app.config["DB_PATH"] = db_path
    ui_app.app.config["TESTING"] = True
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, title, price_eur, status, first_seen_at, last_seen_at, detail_scraped
            ) VALUES (502, 'Renault Clio, 2020', 10000, 'active', datetime('now'), datetime('now'), 0)
            """
        )

    client = ui_app.app.test_client()
    response = client.post("/api/listings/502/engine-volume", json={"liters": "1.6"})
    assert response.status_code == 403

    monkeypatch.setattr(ui_app, "_is_admin", lambda: True)
    response = client.post("/api/listings/502/engine-volume", json={"liters": "1.6"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "id": 502, "liters": 1.6}
