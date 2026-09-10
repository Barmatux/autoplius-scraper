"""Static filter catalogs for index dropdowns."""

from __future__ import annotations

from autoplius.filter_catalogs import (
    BODY_TYPE_OPTIONS,
    FUEL_OPTIONS,
    static_transmission_raw_values,
    static_volume_options,
    static_year_options,
)
from autoplius.transmission_labels import (
    TRANSMISSION_SLUG_AUTO_CLASSIC,
    TRANSMISSION_SLUG_MANUAL,
    classify_transmission_slug,
    transmission_db_values_for_slugs,
)
from scraper.listing_filter_options import ListingFilterOptions


def test_static_volume_options_cover_default_range():
    options = static_volume_options()
    assert "1" in options or "1.0" in options
    assert "1.9" in options
    assert "3" in options or "3.0" in options
    assert options == sorted(options, key=lambda v: float(v.replace(",", ".")))


def test_static_year_options_descend_from_max():
    years = static_year_options(min_year=2008, max_year=2026)
    assert years[0] == 2026
    assert years[-1] == 2008
    assert len(years) == 2026 - 2008 + 1


def test_static_body_and_fuel_are_russian_labels():
    assert "Седан" in BODY_TYPE_OPTIONS
    assert "Дизель" in FUEL_OPTIONS
    assert "Sedanas" not in BODY_TYPE_OPTIONS


def test_static_transmission_maps_slugs_to_db_values():
    raw = static_transmission_raw_values()
    assert classify_transmission_slug("Механическая") == TRANSMISSION_SLUG_MANUAL
    assert classify_transmission_slug("Автоматическая") == TRANSMISSION_SLUG_AUTO_CLASSIC
    manual = transmission_db_values_for_slugs(raw, [TRANSMISSION_SLUG_MANUAL])
    auto = transmission_db_values_for_slugs(raw, [TRANSMISSION_SLUG_AUTO_CLASSIC])
    assert "Механическая" in manual
    assert "Mechaninė" in manual
    assert "Автоматическая" in auto


def test_listing_filter_options_uses_static_spec_fields():
    opts = ListingFilterOptions(
        city_options=[],
        make_model_options={"makes": [], "modelMap": {}, "makeCounts": {}},
        year_options=static_year_options(min_year=2020, max_year=2022),
        body_type_options=list(BODY_TYPE_OPTIONS),
        fuel_options=list(FUEL_OPTIONS),
        transmission_values=static_transmission_raw_values(),
        volume_options=static_volume_options(),
    )
    spec = opts.spec_filters(
        selected_body_types=[],
        selected_fuels=[],
        selected_transmissions=[],
    )
    assert spec["body_type_options"][0] == BODY_TYPE_OPTIONS[0]
    assert "1.9" in spec["volume_options"]
    assert spec["transmission_groups"]
