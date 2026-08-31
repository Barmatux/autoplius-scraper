from __future__ import annotations

from pathlib import Path

from autoplius.parse_listing import parse_listing_html
from autoplius.photo_urls import best_photo_url


FIXTURE = Path(__file__).resolve().parents[2] / "autoplius-parser" / "fixtures" / "listing_detail.html"


def test_parse_all_photos_from_fixture():
    if not FIXTURE.is_file():
        return
    html = FIXTURE.read_text(encoding="utf-8")
    detail = parse_listing_html(html, "https://autoplius.lt/skelbimai/bmw-520-31308999.html")
    assert len(detail.photo_urls) >= 7
    assert all("ann_2_" in url for url in detail.photo_urls if "autoplius-img" in url)


def test_best_photo_url_upgrades_medium_to_full():
    medium = "https://autoplius-img.dgn.lt/ann_3_406812343/bmw-520-0.jpg"
    full = best_photo_url(medium)
    assert full == "https://autoplius-img.dgn.lt/ann_2_406812343/bmw-520-0.jpg"
