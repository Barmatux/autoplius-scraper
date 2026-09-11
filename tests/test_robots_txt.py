"""robots.txt crawl rules for filtered home URLs."""

from __future__ import annotations

from ui.app import app


def test_robots_disallow_query_home():
    client = app.test_client()
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Disallow: /?\n" in text
    assert "User-agent: Googlebot" in text
