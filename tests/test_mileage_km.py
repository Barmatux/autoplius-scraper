from __future__ import annotations

import json

from autoplius.labels import parse_mileage_km, resolve_listing_mileage_km
from scraper.listing_sync import merge_listing_row


def test_parse_mileage_km_strips_spaces_and_units():
    assert parse_mileage_km("134 728 км") == 134728
    assert parse_mileage_km("209.000 km") == 209000
    assert parse_mileage_km(None) is None


def test_resolve_listing_mileage_falls_back_to_parameters():
    item = {
        "mileage_km": None,
        "parameters": {"Пробег": "134 728 км"},
    }
    assert resolve_listing_mileage_km(item) == 134728


def test_merge_preserves_mileage_when_search_update_has_none():
    existing = {
        "autoplius_id": 201,
        "mileage_km": 134728,
        "parameters_json": json.dumps({"Пробег": "134 728 км"}, ensure_ascii=False),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 201,
        "mileage_km": None,
        "parameters_json": "{}",
        "detail_scraped": 0,
        "price_eur": 22000,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=True)
    assert merged["mileage_km"] == 134728


def test_merge_refreshes_mileage_from_parameters_when_missing():
    existing = {
        "autoplius_id": 202,
        "mileage_km": None,
        "parameters_json": json.dumps({"Пробег": "198 000 km"}, ensure_ascii=False),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 202,
        "mileage_km": None,
        "parameters_json": json.dumps({"Пробег": "198 000 km"}, ensure_ascii=False),
        "detail_scraped": 0,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=True)
    assert merged["mileage_km"] == 198000
