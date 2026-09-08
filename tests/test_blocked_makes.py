from autoplius.make_model_filters import (
    BLOCKED_MAKE_MODELS,
    BLOCKED_MAKES,
    is_blocked_listing,
    is_blocked_make,
    is_blocked_make_model,
)


def test_blocked_makes_include_aixam_ligier_microcar_skoda_chatenet_byd_and_daihatsu():
    assert "Aixam" in BLOCKED_MAKES
    assert "Ligier" in BLOCKED_MAKES
    assert "Microcar" in BLOCKED_MAKES
    assert "Skoda" in BLOCKED_MAKES
    assert "Chatenet" in BLOCKED_MAKES
    assert "BYD" in BLOCKED_MAKES
    assert "Daihatsu" in BLOCKED_MAKES
    assert ("Peugeot", "207") in BLOCKED_MAKE_MODELS
    assert is_blocked_make("Aixam")
    assert is_blocked_make("aixam")
    assert is_blocked_make("Ligier")
    assert is_blocked_make("microcar")
    assert is_blocked_make("Skoda")
    assert is_blocked_make("skoda")
    assert is_blocked_make("Chatenet")
    assert is_blocked_make("chatenet")
    assert is_blocked_make("BYD")
    assert is_blocked_make("byd")
    assert is_blocked_make("Daihatsu")
    assert is_blocked_make("daihatsu")
    assert not is_blocked_make("Renault")
    assert not is_blocked_make("Peugeot")
    assert is_blocked_make_model("Peugeot", "207")
    assert is_blocked_make_model("peugeot", "207 CC")
    assert is_blocked_make_model("Peugeot", "207 SW")
    assert not is_blocked_make_model("Peugeot", "3008")
    assert not is_blocked_make_model("Peugeot", "208")


def test_blocked_listings_hidden_from_catalog(tmp_path):
    from scraper.db import fetch_listings, init_db, upsert_listing_item

    db_path = tmp_path / "test.db"
    init_db(db_path)
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 201,
            "title": "Ligier JS50, 2020",
            "price_eur": 9000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 202,
            "title": "Microcar M.Go, 2019",
            "price_eur": 8000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 204,
            "title": "Aixam Crossover, 2022",
            "price_eur": 12000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 203,
            "title": "Renault Clio, 2020",
            "price_eur": 10000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 205,
            "title": "BYD Atto 3, 2023",
            "price_eur": 25000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 206,
            "title": "Chatenet CH26, 2021",
            "price_eur": 7000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 207,
            "title": "Daihatsu Terios, 2018",
            "price_eur": 11000,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 208,
            "title": "Peugeot 207, 2010",
            "price_eur": 3500,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 209,
            "title": "Peugeot 207 CC, 2011",
            "price_eur": 4500,
        },
    )
    upsert_listing_item(
        db_path,
        {
            "autoplius_id": 210,
            "title": "Peugeot 3008, 2019",
            "price_eur": 15000,
        },
    )
    listings = fetch_listings(db_path)
    assert {item["autoplius_id"] for item in listings} == {203, 210}
    assert is_blocked_listing({"title": "Ligier JS50, 2020"})
    assert is_blocked_listing({"title": "Microcar M.Go, 2019"})
    assert is_blocked_listing({"title": "Aixam Crossover, 2022"})
    assert is_blocked_listing({"title": "BYD Atto 3, 2023"})
    assert is_blocked_listing({"title": "Chatenet CH26, 2021"})
    assert is_blocked_listing({"title": "Daihatsu Terios, 2018"})
    assert is_blocked_listing({"title": "Peugeot 207, 2010"})
    assert is_blocked_listing({"title": "Peugeot 207 CC, 2011"})
    assert not is_blocked_listing({"title": "Peugeot 3008, 2019"})


def test_purge_blocked_makes_archives_existing_rows(tmp_path):
    from scraper.db import connect, fetch_engine_catalog, fetch_listings, init_db, purge_blocked_makes

    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, title, price_eur, status, first_seen_at, last_seen_at, detail_scraped
            ) VALUES (301, 'Ligier JS50, 2020', 9000, 'active', datetime('now'), datetime('now'), 0)
            """
        )
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, title, price_eur, status, first_seen_at, last_seen_at, detail_scraped
            ) VALUES (302, 'Peugeot 207, 2010', 3500, 'active', datetime('now'), datetime('now'), 0)
            """
        )
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, title, price_eur, status, first_seen_at, last_seen_at, detail_scraped
            ) VALUES (303, 'Peugeot 3008, 2019', 15000, 'active', datetime('now'), datetime('now'), 0)
            """
        )
        conn.execute(
            """
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, listing_count, is_manual, is_new, updated_at
            ) VALUES ('Ligier', 'JS50', '0.5 l', 'Benzinas', 1, 0, 0, datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, listing_count, is_manual, is_new, updated_at
            ) VALUES ('Peugeot', '207', '1.4 l', 'Benzinas', 1, 0, 0, datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, listing_count, is_manual, is_new, updated_at
            ) VALUES ('Peugeot', '207 CC', '1.6 l', 'Benzinas', 1, 0, 0, datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, listing_count, is_manual, is_new, updated_at
            ) VALUES ('Peugeot', '3008', '1.6 l', 'Dyzelinas', 1, 0, 0, datetime('now'))
            """
        )

    result = purge_blocked_makes(db_path)
    assert result["archived_listings"] == 2
    assert result["catalog_removed"] == 3
    remaining = fetch_listings(db_path)
    assert len(remaining) == 1
    assert remaining[0]["autoplius_id"] == 303
    catalog = fetch_engine_catalog(db_path)
    assert len(catalog) == 1
    assert catalog[0]["make"] == "Peugeot"
    assert catalog[0]["model"] == "3008"
