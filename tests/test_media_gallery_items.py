from __future__ import annotations

from autoplius.parse_listing import _parse_media_gallery_items, parse_listing_html
from bs4 import BeautifulSoup


NESTED_GALLERY_HTML = """
<html><head><title>BMW</title></head><body>
<h1>BMW X1</h1>
<div class="second-parameters"><div class="parameter-row">
  <div class="parameter-label">Metai</div><div class="parameter-value">2023</div>
</div></div>
<script>
var mediaGalleryItems = [
  {"type":"photo","url":"https://autoplius-img.dgn.lt/ann_3_111/a.jpg","sizes":[100,200,300]},
  {"type":"photo","url":"https://autoplius-img.dgn.lt/ann_25_222/b.jpg"},
  {"type":"video","url":"https://example.com/x.mp4"},
  {"type":"photo","thumbnail":"https://autoplius-img.dgn.lt/ann_3_333/c.jpg"}
];
</script>
</body></html>
"""


def test_media_gallery_items_with_nested_arrays():
    soup = BeautifulSoup(NESTED_GALLERY_HTML, "html.parser")
    urls = _parse_media_gallery_items(soup)
    assert len(urls) == 3
    assert all("ann_2_" in url for url in urls)


def test_parse_listing_collects_gallery_photos():
    detail = parse_listing_html(
        NESTED_GALLERY_HTML,
        "https://ru.autoplius.lt/objavlenija/bmw-x1-32154344.html",
    )
    assert detail.autoplius_id == 32154344
    assert len(detail.photo_urls) == 3
