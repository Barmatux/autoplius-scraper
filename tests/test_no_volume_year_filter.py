from __future__ import annotations

from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters


def _insert_listing(conn, listing_id: int, title: str, *, year: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO listings (
            autoplius_id, title, year, price_eur, status, first_seen_at, last_seen_at, detail_scraped
        ) VALUES (?, ?, ?, 10000, 'active', datetime('now'), datetime('now'), 0)
        """,
        (listing_id, title, year),
    )


def test_no_volume_tab_excludes_cars_older_than_2008(tmp_path):
    from scraper.db import connect, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        _insert_listing(conn, 401, "Renault Clio, 2007", year="2007-01")
        _insert_listing(conn, 402, "Renault Clio, 2008", year="2008-03")
        _insert_listing(conn, 403, "Renault Clio, 2020", year="2020-05")

    filters = ListingFilters(engine_volume_missing=True, catalog_filter=False)
    ids = fetch_listing_ids(db_path, filters)
    assert ids == [402, 403]
    assert count_listings(db_path, filters) == 2
