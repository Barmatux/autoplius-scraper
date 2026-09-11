"""Tests for listing URL normalization (SEO + cache keys)."""

from __future__ import annotations

from autoplius.listing_url_normalize import (
    default_equivalent_home_target,
    listing_query_has_active_filters,
    normalize_listing_cache_query,
)


def test_normalize_drops_defaults_and_empties():
    assert (
        normalize_listing_cache_query(
            "tab=all&sort=added_desc&page=1&q=&make=&upto_19l=1&over_3y=1&passable=0"
        )
        == ""
    )


def test_normalize_keeps_real_filters_sorted():
    assert normalize_listing_cache_query("model=Golf&make=VW&sort=price_asc") == (
        "make=VW&model=Golf&sort=price_asc"
    )


def test_normalize_keeps_cards_view():
    assert normalize_listing_cache_query("view=cards&tab=all") == "view=cards"


def test_active_filters_detect_make_and_tab():
    assert not listing_query_has_active_filters("")
    assert not listing_query_has_active_filters("tab=all&sort=added_desc")
    assert listing_query_has_active_filters("make=BMW")
    assert listing_query_has_active_filters("tab=electric")
    assert listing_query_has_active_filters("upto_19l=0")
    assert listing_query_has_active_filters("passable=1")


def test_default_equivalent_redirect_targets():
    assert default_equivalent_home_target("") is None
    assert default_equivalent_home_target("tab=all&sort=added_desc") == "/"
    assert default_equivalent_home_target("q=&make=&tab=all") == "/"
    assert default_equivalent_home_target("view=cards") is None
    assert default_equivalent_home_target("view=cards&tab=all") == "/?view=cards"
    assert default_equivalent_home_target("make=BMW") is None
