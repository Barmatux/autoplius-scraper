#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from autoplius.browser import create_browser_context, goto_and_wait
from autoplius.urls import configure_base_url, get_base_url

configure_base_url("https://ru.autoplius.lt")
base = get_base_url()

MAKES = {
    "peugeot": ["3008", "5008"],
    "nissan": ["qashqai"],
    "renault": ["grand-scenic", "scenic"],
    "hyundai": ["i40"],
    "kia": ["optima"],
    "ford": ["s-max", "galaxy"],
}

with sync_playwright() as pw:
    ctx, page = create_browser_context(
        pw,
        headless=True,
        profile_dir=Path("/var/lib/autoplius-scraper/browser-profile"),
        storage_state=None,
    )
    try:
        for make_slug, models in MAKES.items():
            url = f"{base}/objavlenija/b-u-avtomobili/{make_slug}?category_id=2"
            goto_and_wait(page, url, timeout_sec=120, auto_captcha=True, captcha_api_key=None)
            html = page.content()
            make_ids = set(re.findall(r"make_id_list=(\d+)", html))
            print(f"MAKE {make_slug} url={page.url} make_ids={sorted(make_ids)[:5]}")
            for model_slug in models:
                model_url = f"{base}/objavlenija/b-u-avtomobili/{make_slug}/{model_slug}?category_id=2"
                goto_and_wait(page, model_url, timeout_sec=120, auto_captcha=True, captcha_api_key=None)
                html = page.content()
                model_ids = set(re.findall(r"model_id_list=(\d+)", html))
                make_ids = set(re.findall(r"make_id_list=(\d+)", html))
                print(
                    f"  MODEL {model_slug} url={page.url} "
                    f"make_ids={sorted(make_ids)[:3]} model_ids={sorted(model_ids)[:3]}"
                )
    finally:
        ctx.close()
