from __future__ import annotations

import json

from scraper.listing_sync import merge_listing_row


def test_merge_preserves_minio_photo_when_search_update_has_no_photo():
    existing = {
        "autoplius_id": 101,
        "photo_url": "/media/object?key=listings/101/000.jpg",
        "photo_urls_json": json.dumps(["/media/object?key=listings/101/000.jpg"]),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 101,
        "photo_url": None,
        "photo_urls_json": "[]",
        "detail_scraped": 0,
        "price_eur": 9000,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=False)
    assert merged["photo_url"] == existing["photo_url"]
    assert merged["photo_urls_json"] == existing["photo_urls_json"]


def test_merge_preserves_engine_liters_when_search_update_has_none():
    existing = {
        "autoplius_id": 103,
        "engine_liters": 1.6,
        "parameters_json": json.dumps({"Двигатель": "1598 см³"}, ensure_ascii=False),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 103,
        "engine_liters": None,
        "parameters_json": "{}",
        "detail_scraped": 0,
        "price_eur": 5000,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=True)
    assert merged["engine_liters"] == 1.6
    assert "1598" in merged["parameters_json"]


def test_merge_refreshes_engine_liters_from_parameters_when_missing():
    existing = {
        "autoplius_id": 104,
        "engine_liters": None,
        "parameters_json": json.dumps(
            {"Двигатель": "1461 см³", "Объём двигателя, см³": "1.5 л"},
            ensure_ascii=False,
        ),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 104,
        "engine_liters": None,
        "parameters_json": "{}",
        "detail_scraped": 0,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=True)
    assert merged["engine_liters"] == 1.5
