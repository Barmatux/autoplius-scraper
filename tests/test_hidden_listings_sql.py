from scraper.listing_sql_filters import ListingFilters, build_listing_where


def test_no_volume_tab_sql_excludes_skoda_and_pickups():
    filters = ListingFilters(engine_volume_missing=True, catalog_filter=False)
    where, params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "engine_liters IS NULL" in sql
    assert "skoda%" in params
    assert "pikap" in sql.lower() or "pickup" in sql.lower()


def test_skoda_hidden_when_catalog_filter_disabled():
    filters = ListingFilters(catalog_filter=False, exclude_blocked_makes=True)
    where, _params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "skoda" in " ".join(str(p) for p in _params).lower() or any(
        "skoda" in str(p).lower() for p in _params
    )
