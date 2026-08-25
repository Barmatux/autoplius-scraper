from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import sync_playwright

from autoplius.browser import (
    TurnstileInterceptor,
    create_browser_context,
    goto_and_wait,
    resolve_captcha_api_key,
)
from autoplius.captcha import CaptchaError, get_balance
from autoplius.models import SearchListingPreview
from autoplius.parse_search import parse_search_html
from autoplius.urls import build_search_url

from scraper.config import Settings
from scraper.storage import diff_stats, load_latest_ids, save_snapshot

logger = logging.getLogger(__name__)


@dataclass
class ScrapeRunResult:
    payload: dict[str, Any]
    snapshot_path: str
    diff: dict[str, int]


def scrape_search_pages(settings: Settings) -> ScrapeRunResult:
    started_at = datetime.now(timezone.utc)
    previous_ids = load_latest_ids(settings.data_dir)

    captcha_api_key = None
    if settings.auto_captcha:
        captcha_api_key = resolve_captcha_api_key(True)
        balance = get_balance(captcha_api_key)
        logger.info("2Captcha balance: $%.4f", balance)

    interceptor = TurnstileInterceptor() if settings.auto_captcha else None
    all_listings: dict[int, SearchListingPreview] = {}
    page_stats: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser_or_context, page = create_browser_context(
            pw,
            headless=settings.headless,
            profile_dir=settings.profile_dir,
            storage_state=None,
            interceptor=interceptor,
        )
        try:
            for page_num in range(1, settings.pages + 1):
                url = build_search_url(page=page_num)
                logger.info("Fetching page %s/%s: %s", page_num, settings.pages, url)

                goto_and_wait(
                    page,
                    url,
                    timeout_sec=settings.timeout_sec,
                    auto_captcha=settings.auto_captcha,
                    captcha_api_key=captcha_api_key,
                    interceptor=interceptor,
                )

                previews = parse_search_html(page.content())
                new_on_page = 0
                for preview in previews:
                    if preview.autoplius_id not in all_listings:
                        new_on_page += 1
                    all_listings[preview.autoplius_id] = preview

                page_stats.append(
                    {
                        "page": page_num,
                        "url": url,
                        "count": len(previews),
                        "new_unique": new_on_page,
                    }
                )
                logger.info(
                    "Page %s: %s listings (%s new unique, total %s)",
                    page_num,
                    len(previews),
                    new_on_page,
                    len(all_listings),
                )

                if page_num < settings.pages:
                    time.sleep(settings.page_delay_sec)
        finally:
            browser_or_context.close()

    finished_at = datetime.now(timezone.utc)
    listings = [item.to_dict() for item in all_listings.values()]
    current_ids = set(all_listings.keys())
    diff = diff_stats(current_ids, previous_ids)

    payload: dict[str, Any] = {
        "mode": "test" if settings.test_mode else "prod",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_sec": round((finished_at - started_at).total_seconds(), 2),
        "pages_scraped": settings.pages,
        "listing_count": len(listings),
        "page_stats": page_stats,
        "diff_vs_previous": diff,
        "listings": listings,
    }

    snapshot_path = save_snapshot(
        payload,
        data_dir=settings.data_dir,
        test_mode=settings.test_mode,
    )

    logger.info(
        "Done: %s listings from %s pages | new=%s removed=%s unchanged=%s",
        len(listings),
        settings.pages,
        diff["new"],
        diff["removed"],
        diff["unchanged"],
    )
    return ScrapeRunResult(payload=payload, snapshot_path=str(snapshot_path), diff=diff)


def run_job(settings: Settings) -> ScrapeRunResult:
    logger.info(
        "Starting scrape (test_mode=%s, pages=%s, auto_captcha=%s)",
        settings.test_mode,
        settings.pages,
        settings.auto_captcha,
    )
    try:
        return scrape_search_pages(settings)
    except CaptchaError as exc:
        logger.error("Captcha error: %s", exc)
        raise
    except Exception:
        logger.exception("Scrape failed")
        raise
