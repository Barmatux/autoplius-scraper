#!/usr/bin/env python3
"""Quick check: does a target query return listings?"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from autoplius.browser import create_browser_context, goto_and_wait
from autoplius.parse_search import parse_search_html
from autoplius.target_queries import build_target_queries
from autoplius.urls import build_search_url, configure_base_url

query = build_target_queries(root=ROOT)[0]
configure_base_url("https://ru.autoplius.lt")
url = build_search_url(page=1, **query.build_kwargs())
print("URL:", url)

with sync_playwright() as pw:
    ctx, page = create_browser_context(
        pw,
        headless=True,
        profile_dir=Path("/var/lib/autoplius-scraper/browser-profile"),
    )
    try:
        goto_and_wait(page, url, timeout_sec=120, auto_captcha=True, captcha_api_key=None)
        previews = parse_search_html(page.content())
        print("listings:", len(previews))
        if previews:
            print("sample:", previews[0].title, previews[0].autoplius_id)
    finally:
        ctx.close()
