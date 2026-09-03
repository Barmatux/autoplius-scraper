from __future__ import annotations

import json
import sqlite3

from scraper.db import _preserve_stored_photos


def _row(**kwargs) -> sqlite3.Row:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cols = ", ".join(kwargs)
    placeholders = ", ".join("?" for _ in kwargs)
    conn.execute(f"CREATE TABLE t ({cols})")
    conn.execute(f"INSERT INTO t VALUES ({placeholders})", tuple(kwargs.values()))
    return conn.execute("SELECT * FROM t").fetchone()


def test_preserve_allows_richer_external_gallery_over_single_minio():
    existing = _row(
        photo_url="/media/object?key=listings/101/000.jpg",
        photo_urls_json=json.dumps(["/media/object?key=listings/101/000.jpg"]),
    )
    row = {
        "photo_url": "https://autoplius-img.dgn.lt/ann_2_aaa.jpg",
        "photo_urls_json": json.dumps(
            [
                "https://autoplius-img.dgn.lt/ann_2_aaa.jpg",
                "https://autoplius-img.dgn.lt/ann_2_bbb.jpg",
                "https://autoplius-img.dgn.lt/ann_2_ccc.jpg",
            ]
        ),
        "detail_scraped": 1,
    }
    _preserve_stored_photos(row, existing)
    assert "ann_2_bbb" in row["photo_urls_json"]
    assert row["photo_url"].startswith("https://")


def test_preserve_keeps_minio_when_search_refresh_has_one_external_thumb():
    existing = _row(
        photo_url="/media/object?key=listings/101/000.jpg",
        photo_urls_json=json.dumps(
            [
                "/media/object?key=listings/101/000.jpg",
                "/media/object?key=listings/101/001.jpg",
            ]
        ),
    )
    row = {
        "photo_url": "https://autoplius-img.dgn.lt/ann_3_aaa.jpg",
        "photo_urls_json": json.dumps(["https://autoplius-img.dgn.lt/ann_3_aaa.jpg"]),
        "detail_scraped": 0,
    }
    _preserve_stored_photos(row, existing)
    assert row["photo_url"].startswith("/media/object")
    assert "001.jpg" in row["photo_urls_json"]
