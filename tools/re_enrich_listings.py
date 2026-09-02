#!/usr/bin/env python3
"""Re-fetch listing detail pages and refresh photos in DB + MinIO."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.browser import (
    TurnstileInterceptor,
    create_browser_context,
    goto_and_wait,
    resolve_captcha_api_key,
)
from autoplius.captcha import get_balance
from autoplius.parse_listing import parse_listing_html
from autoplius.urls import configure_base_url
from playwright.sync_api import sync_playwright
from scraper.config import Settings
from scraper.db import fetch_listing, update_listing_detail
from scraper.photo_sync import sync_listing_photos

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-enrich listing detail pages")
    parser.add_argument("listing_ids", nargs="+", type=int, help="Autoplius listing IDs")
    parser.add_argument("--sync-photos", action="store_true", help="Upload refreshed photos to MinIO")
    parser.add_argument("--force-photos", action="store_true", help="Overwrite existing MinIO objects")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between listings (seconds)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    configure_base_url(settings.autoplius_base_url)

    captcha_api_key = None
    interceptor = None
    if settings.auto_captcha:
        captcha_api_key = resolve_captcha_api_key(True)
        balance = get_balance(captcha_api_key)
        logger.info("2Captcha balance: $%.4f", balance)
        interceptor = TurnstileInterceptor()

    with sync_playwright() as pw:
        browser_or_context, page = create_browser_context(
            pw,
            headless=settings.headless,
            profile_dir=None,
            storage_state=None,
            interceptor=interceptor,
        )
        try:
            for idx, listing_id in enumerate(args.listing_ids, start=1):
                item = fetch_listing(settings.db_path, listing_id)
                if not item:
                    logger.warning("Listing %s not found", listing_id)
                    continue
                url = item.get("url")
                if not url:
                    logger.warning("Listing %s has no URL", listing_id)
                    continue

                logger.info("[%s/%s] Re-enrich %s", idx, len(args.listing_ids), url)
                if idx > 1 and args.delay > 0:
                    time.sleep(args.delay)

                try:
                    goto_and_wait(
                        page,
                        url,
                        timeout_sec=settings.timeout_sec,
                        auto_captcha=settings.auto_captcha,
                        captcha_api_key=captcha_api_key,
                        interceptor=interceptor,
                    )
                except Exception as exc:
                    logger.warning("  skip: %s", exc)
                    continue

                detail = parse_listing_html(page.content(), url)
                update_listing_detail(settings.db_path, listing_id, detail.to_dict())
                logger.info(
                    "  photos=%s title=%s",
                    len(detail.photo_urls),
                    (detail.title or "")[:60],
                )

                if args.sync_photos and settings.s3_enabled:
                    refreshed = fetch_listing(settings.db_path, listing_id) or item
                    status, uploaded, detail_msg = sync_listing_photos(
                        settings,
                        refreshed,
                        timeout=settings.sync_photos_timeout_sec,
                        force=args.force_photos,
                    )
                    suffix = f" ({detail_msg})" if detail_msg else ""
                    logger.info("  photo sync: %s uploaded=%s%s", status, uploaded, suffix)
        finally:
            browser_or_context.close()


if __name__ == "__main__":
    main()
