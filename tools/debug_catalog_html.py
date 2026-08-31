#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from autoplius.browser import create_browser_context, goto_and_wait
from autoplius.urls import build_search_url, configure_base_url

configure_base_url("https://ru.autoplius.lt")
url = build_search_url(page=1, extra={"category_id": 2})

with sync_playwright() as pw:
    ctx, page = create_browser_context(
        pw,
        headless=True,
        profile_dir=Path("/var/lib/autoplius-scraper/browser-profile"),
        storage_state=None,
    )
    try:
        goto_and_wait(page, url, timeout_sec=120, auto_captcha=True, captcha_api_key=None)
        html = page.content()
        for name in ("Peugeot", "Nissan", "Renault", "Hyundai", "Kia", "Ford", "3008", "Qashqai"):
            idx = html.lower().find(name.lower())
            print(f"=== {name} idx={idx} ===")
            if idx >= 0:
                print(html[max(0, idx - 120) : idx + 200].replace("\n", " "))
        ids = re.findall(r"make_id_list=(\d+)[^\"'<>]{0,80}Peugeot", html, flags=re.I)
        print("make_id near Peugeot:", ids[:5])
        ids2 = re.findall(r"Peugeot[^\"'<>]{0,80}make_id_list=(\d+)", html, flags=re.I)
        print("make_id after Peugeot:", ids2[:5])
        print("html length", len(html))
    finally:
        ctx.close()
