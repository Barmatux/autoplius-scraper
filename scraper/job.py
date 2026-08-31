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
from autoplius.parse_listing import parse_listing_html
from autoplius.parse_search import parse_search_html
from autoplius.labels import promote_parameters
from autoplius.translate import translate_to_russian
from autoplius.urls import build_search_url, configure_base_url

from scraper.config import Settings
from scraper.db import save_payload_to_db
from scraper.photo_sync import sync_run_photos
from scraper.storage import diff_stats, load_latest_ids, save_snapshot

logger = logging.getLogger(__name__)


@dataclass
class ScrapeRunResult:
    payload: dict[str, Any]
    snapshot_path: str
    diff: dict[str, int]


def merge_preview_and_detail(
    preview: SearchListingPreview,
    *,
    detail: dict[str, Any] | None = None,
    error: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    row = preview.to_dict()
    if detail:
        # Prefer richer detail values when present.
        if detail.get("title"):
            row["title"] = detail["title"]
        if detail.get("price_eur") is not None:
            row["price_eur"] = detail["price_eur"]
        row["description"] = detail.get("description")
        row["phone"] = detail.get("phone")
        row["vin_masked"] = detail.get("vin_masked")
        row["parameters"] = detail.get("parameters") or {}
        row["photo_urls"] = detail.get("photo_urls") or []
        if row["photo_urls"] and not row.get("photo_url"):
            row["photo_url"] = row["photo_urls"][0]
        params = row["parameters"]
        promote_parameters(row, params)
        original_description = row.get("description")
        if settings and original_description:
            row["description_ru"] = translate_to_russian(
                original_description,
                enabled=settings.translate_descriptions,
                min_delay_sec=settings.translate_delay_sec,
            )
        row["detail_scraped"] = True
        row["detail_error"] = None
    else:
        row.setdefault("description", None)
        row.setdefault("description_ru", None)
        row.setdefault("phone", None)
        row.setdefault("vin_masked", None)
        row.setdefault("parameters", {})
        row.setdefault("photo_urls", [row["photo_url"]] if row.get("photo_url") else [])
        row["detail_scraped"] = False
        row["detail_error"] = error
    return row


def scrape_search_pages(settings: Settings) -> ScrapeRunResult:
    started_at = datetime.now(timezone.utc)
    previous_ids = load_latest_ids(settings.data_dir)
    configure_base_url(settings.autoplius_base_url)

    captcha_api_key = None
    if settings.auto_captcha:
        captcha_api_key = resolve_captcha_api_key(True)
        balance = get_balance(captcha_api_key)
        logger.info("2Captcha balance: $%.4f", balance)

    interceptor = TurnstileInterceptor() if settings.auto_captcha else None
    all_previews: dict[int, SearchListingPreview] = {}
    page_stats: list[dict[str, Any]] = []
    detail_ok = 0
    detail_fail = 0

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
                    if preview.autoplius_id not in all_previews:
                        new_on_page += 1
                    all_previews[preview.autoplius_id] = preview

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
                    len(all_previews),
                )

                if page_num < settings.pages:
                    time.sleep(settings.page_delay_sec)

            listings: list[dict[str, Any]] = []
            preview_list = list(all_previews.values())
            if settings.enrich_details:
                limit = settings.enrich_limit if settings.enrich_limit > 0 else len(preview_list)
                to_enrich = preview_list[:limit]
                skip = preview_list[limit:]
                logger.info(
                    "Enriching %s/%s listing detail pages (delay=%ss)",
                    len(to_enrich),
                    len(preview_list),
                    settings.detail_delay_sec,
                )
                for idx, preview in enumerate(to_enrich, start=1):
                    logger.info(
                        "Detail %s/%s: %s",
                        idx,
                        len(to_enrich),
                        preview.url,
                    )
                    try:
                        time.sleep(settings.detail_delay_sec)
                        goto_and_wait(
                            page,
                            preview.url,
                            timeout_sec=settings.timeout_sec,
                            auto_captcha=settings.auto_captcha,
                            captcha_api_key=captcha_api_key,
                            interceptor=interceptor,
                        )
                        detail = parse_listing_html(page.content(), preview.url).to_dict()
                        listings.append(merge_preview_and_detail(preview, detail=detail, settings=settings))
                        detail_ok += 1
                    except Exception as exc:
                        detail_fail += 1
                        logger.warning("Detail failed for %s: %s", preview.autoplius_id, exc)
                        listings.append(
                            merge_preview_and_detail(preview, error=str(exc)[:300], settings=settings)
                        )
                for preview in skip:
                    listings.append(merge_preview_and_detail(preview, settings=settings))
            else:
                listings = [merge_preview_and_detail(p, settings=settings) for p in preview_list]
        finally:
            browser_or_context.close()

    finished_at = datetime.now(timezone.utc)
    current_ids = {item["autoplius_id"] for item in listings}
    diff = diff_stats(current_ids, previous_ids)

    payload: dict[str, Any] = {
        "mode": "test" if settings.test_mode else "prod",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_sec": round((finished_at - started_at).total_seconds(), 2),
        "pages_scraped": settings.pages,
        "listing_count": len(listings),
        "details_scraped": detail_ok,
        "details_failed": detail_fail,
        "enrich_details": settings.enrich_details,
        "page_stats": page_stats,
        "diff_vs_previous": diff,
        "listings": listings,
    }

    snapshot_path = save_snapshot(
        payload,
        data_dir=settings.data_dir,
        test_mode=settings.test_mode,
    )
    run_id = save_payload_to_db(
        settings.db_path,
        payload,
        snapshot_path=str(snapshot_path),
    )

    photo_sync = sync_run_photos(settings, listings)
    payload["photo_sync"] = photo_sync

    logger.info(
        "Done: %s listings, details ok=%s fail=%s | new=%s removed=%s unchanged=%s | db_run_id=%s | photos uploaded=%s",
        len(listings),
        detail_ok,
        detail_fail,
        diff["new"],
        diff["removed"],
        diff["unchanged"],
        run_id,
        photo_sync.get("uploaded", 0),
    )
    return ScrapeRunResult(payload=payload, snapshot_path=str(snapshot_path), diff=diff)


def run_job(settings: Settings) -> ScrapeRunResult:
    logger.info(
        "Starting scrape (test_mode=%s, pages=%s, enrich=%s, auto_captcha=%s)",
        settings.test_mode,
        settings.pages,
        settings.enrich_details,
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
