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


def test_merge_replaces_photo_when_incoming_has_new_urls():
    existing = {
        "autoplius_id": 102,
        "photo_url": "/media/object?key=listings/102/old.jpg",
        "photo_urls_json": json.dumps(["/media/object?key=listings/102/old.jpg"]),
        "detail_scraped": 1,
        "manual_overrides_json": None,
    }
    incoming = {
        "autoplius_id": 102,
        "photo_url": "https://autoplius-img.dgn.lt/ann_2_/new.jpg",
        "photo_urls_json": json.dumps(["https://autoplius-img.dgn.lt/ann_2_/new.jpg"]),
        "detail_scraped": 1,
    }
    merged = merge_listing_row(existing, incoming, keep_detail=False)
    assert "new.jpg" in merged["photo_url"]
