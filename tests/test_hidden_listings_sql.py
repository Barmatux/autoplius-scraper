from scraper.listing_sql_filters import ListingFilters, build_listing_where


def test_vehicle_filter_matches_space_separated_title():
    filters = ListingFilters(
        vehicle_rows=[{"make": "Peugeot", "model": "3008"}],
        catalog_filter=False,
    )
    where, params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "lower(COALESCE(title, '')) LIKE ?" in sql
    assert "peugeot 3008%" in params
    assert "peugeot,%3008%" in params


def test_vehicle_filter_make_only_matches_space_or_comma():
    filters = ListingFilters(
        vehicle_rows=[{"make": "Volvo", "model": ""}],
        catalog_filter=False,
    )
    _where, params = build_listing_where(filters)
    assert "volvo %" in params
    assert "volvo,%" in params


def test_no_volume_tab_sql_excludes_skoda_and_pickups():
    filters = ListingFilters(engine_volume_missing=True, catalog_filter=False)
    where, params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "engine_liters IS NULL" in sql
    assert "manual_electric" in sql
    assert "лектр" in sql
    assert "skoda%" in params
    assert "pikap" in sql.lower() or "pickup" in sql.lower()


def test_electric_tab_sql_includes_manual_and_fuel():
    filters = ListingFilters(electric_only=True, catalog_filter=False)
    where, _params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "COALESCE(manual_electric, 0) = 1" in sql
    assert "лектр" in sql
    assert "engine_liters IS NULL" not in sql

def test_skoda_hidden_when_catalog_filter_disabled():
    filters = ListingFilters(catalog_filter=False, exclude_blocked_makes=True)
    where, _params = build_listing_where(filters)
    sql = " AND ".join(where)
    assert "skoda" in " ".join(str(p) for p in _params).lower() or any(
        "skoda" in str(p).lower() for p in _params
    )
