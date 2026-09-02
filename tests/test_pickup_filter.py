from autoplius.catalog_filters import is_pickup_body_type, is_pickup_listing


def test_is_pickup_body_type():
    assert is_pickup_body_type("Pikapas")
    assert is_pickup_body_type("Пикап")
    assert is_pickup_body_type("pickup")
    assert not is_pickup_body_type("Sedanas")
    assert not is_pickup_body_type(None)


def test_pickup_hidden_from_catalog():
    from autoplius.catalog_filters import is_catalog_visible

    assert not is_catalog_visible({"title": "Ford Ranger, Pikapas 2020", "body_type": "Pikapas"})
    assert is_catalog_visible({"title": "BMW 320, Sedanas 2020", "body_type": "Sedanas"})


def test_pickup_listings_are_not_inserted(tmp_path):
    from scraper.db import fetch_listings, init_db, upsert_listing_item

    db_path = tmp_path / "test.db"
    init_db(db_path)
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 101,
            "title": "Ford Ranger, Pikapas 2020",
            "body_type": "Pikapas",
            "price_eur": 10000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 102,
            "title": "BMW 320, Sedanas 2020",
            "body_type": "Sedanas",
            "price_eur": 12000,
        },
    )
    listings = fetch_listings(db_path)
    assert len(listings) == 1
    assert listings[0]["autoplius_id"] == 102
