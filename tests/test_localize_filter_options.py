from autoplius.localize import (
    expand_filter_value_variants,
    localize_value,
    unique_localized_options,
)
from scraper.listing_sql_filters import ListingFilters, build_listing_where


def test_localize_missing_body_types():
    assert localize_value("Limuzinas") == "Лимузин"
    assert localize_value("Keleivinis mikroautobusas") == "Пассажирский микроавтобус"
    assert localize_value("Krovininis mikroautobusas") == "Грузовой микроавтобус"


def test_unique_localized_options_dedupes_lt_and_ru():
    assert unique_localized_options(["Sedanas", "Седан", "Hečbekas", "Хэтчбек"]) == [
        "Седан",
        "Хэтчбек",
    ]


def test_expand_filter_value_variants_includes_lt_synonyms():
    variants = expand_filter_value_variants(["Седан"])
    assert "Седан" in variants
    assert "Sedanas" in variants


def test_build_listing_where_body_type_matches_lt_rows():
    clauses, params = build_listing_where(ListingFilters(body_types=["Седан"]))
    assert any("body_type" in clause for clause in clauses)
    assert "Седан" in params
    assert "Sedanas" in params
