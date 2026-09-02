from autoplius.make_model_filters import BLOCKED_MAKES, is_blocked_make, is_blocked_listing


def test_blocked_makes_include_aixam_ligier_microcar_and_skoda():
    assert "Aixam" in BLOCKED_MAKES
    assert "Ligier" in BLOCKED_MAKES
    assert "Microcar" in BLOCKED_MAKES
    assert "Skoda" in BLOCKED_MAKES
    assert is_blocked_make("Aixam")
    assert is_blocked_make("aixam")
    assert is_blocked_make("Ligier")
    assert is_blocked_make("microcar")
    assert is_blocked_make("Skoda")
    assert is_blocked_make("skoda")
    assert not is_blocked_make("Renault")


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
    listings = fetch_listings(db_path)
    assert len(listings) == 1
    assert listings[0]["autoplius_id"] == 203
    assert is_blocked_listing({"title": "Ligier JS50, 2020"})
    assert is_blocked_listing({"title": "Microcar M.Go, 2019"})
    assert is_blocked_listing({"title": "Aixam Crossover, 2022"})


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
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, listing_count, is_manual, is_new, updated_at
            ) VALUES ('Ligier', 'JS50', '0.5 l', 'Benzinas', 1, 0, 0, datetime('now'))
            """
        )

    result = purge_blocked_makes(db_path)
    assert result["archived_listings"] == 1
    assert result["catalog_removed"] == 1
    assert not fetch_listings(db_path)
    assert not fetch_engine_catalog(db_path)
