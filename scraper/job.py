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
from autoplius.localize import localize_listing
from autoplius.search_query import SearchQuery
from autoplius.translate import translate_to_russian
from autoplius.urls import build_search_url, configure_base_url

from scraper.config import Settings
from scraper.db import (
    hours_since_last_full_scrape,
    load_detail_scraped_ids,
    load_known_ids,
    save_payload_to_db,
)
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
        for key in ("price_net_eur", "price_gross_eur", "price_vat_note"):
            if detail.get(key) is not None:
                row[key] = detail[key]
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
    return localize_listing(row)


def resolve_scrape_mode(settings: Settings) -> tuple[bool, str]:
    """Return (incremental, reason)."""
    if not settings.incremental_scrape:
        return False, "INCREMENTAL_SCRAPE=false"
    hours = hours_since_last_full_scrape(settings.db_path)
    if hours is None:
        return False, "no prior full scrape in database"
    if hours >= settings.full_scrape_interval_hours:
        return False, f"full refresh due ({hours:.1f}h since last full scrape)"
    return True, f"incremental ({hours:.1f}h since last full scrape)"


def scrape_search_pages(
    settings: Settings,
    *,
    queries: list[SearchQuery] | None = None,
    paginate_until_empty: bool = False,
    update_latest_snapshot: bool = True,
    archive_removed: bool | None = None,
) -> ScrapeRunResult:
    started_at = datetime.now(timezone.utc)
    previous_ids = load_latest_ids(settings.data_dir) if update_latest_snapshot else set()
    known_ids = load_known_ids(settings.db_path)
    detail_scraped_ids = load_detail_scraped_ids(settings.db_path)
    target_mode = bool(queries)
    if target_mode:
        incremental = False
        mode_reason = f"target batch ({len(queries)} queries)"
        paginate_until_empty = True
        if archive_removed is None:
            archive_removed = False
        update_latest_snapshot = False
    else:
        incremental, mode_reason = resolve_scrape_mode(settings)
        if archive_removed is None:
            archive_removed = settings.archive_removed_on_full_scrape
    configure_base_url(settings.autoplius_base_url)
    newest_first = settings.search_newest_first and incremental and not target_mode

    logger.info(
        "Scrape mode: %s (%s)",
        "target" if target_mode else ("incremental" if incremental else "full"),
        mode_reason,
    )

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
    pages_scraped = 0
    consecutive_empty_pages = 0

    query_plan = queries or [None]
    total_queries = len(query_plan)

    with sync_playwright() as pw:
        browser_or_context, page = create_browser_context(
            pw,
            headless=settings.headless,
            profile_dir=settings.profile_dir,
            storage_state=None,
            interceptor=interceptor,
        )
        try:
            for query_idx, query in enumerate(query_plan, start=1):
                if query:
                    logger.info(
                        "Target query %s/%s: %s",
                        query_idx,
                        total_queries,
                        query.label,
                    )
                consecutive_empty_pages = 0
                query_previews: dict[int, SearchListingPreview] = {}

                for page_num in range(1, settings.pages + 1):
                    search_kwargs: dict[str, object] = {}
                    if query is not None:
                        search_kwargs = query.build_kwargs()
                    url = build_search_url(
                        page=page_num,
                        newest_first=newest_first,
                        **search_kwargs,
                    )
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
                    if paginate_until_empty and not previews:
                        logger.info(
                            "Empty page %s for query %s — stopping pagination",
                            page_num,
                            query.label if query else "default",
                        )
                        break

                    new_on_page = 0
                    for preview in previews:
                        is_new = preview.autoplius_id not in known_ids
                        if preview.autoplius_id not in query_previews:
                            if is_new:
                                new_on_page += 1
                        query_previews[preview.autoplius_id] = preview
                        all_previews[preview.autoplius_id] = preview

                    pages_scraped += 1
                    page_stats.append(
                        {
                            "query": query.label if query else None,
                            "page": page_num,
                            "url": url,
                            "count": len(previews),
                            "new_unique": new_on_page,
                        }
                    )
                    logger.info(
                        "Page %s (%s): %s listings (%s new vs DB, query total %s, run total %s)",
                        page_num,
                        query.label if query else "default",
                        len(previews),
                        new_on_page,
                        len(query_previews),
                        len(all_previews),
                    )

                    if incremental:
                        if new_on_page == 0:
                            consecutive_empty_pages += 1
                            if (
                                consecutive_empty_pages
                                >= settings.incremental_stop_empty_pages
                            ):
                                logger.info(
                                    "Stopping incremental scrape after %s page(s) with no new listings",
                                    consecutive_empty_pages,
                                )
                                break
                        else:
                            consecutive_empty_pages = 0

                    if page_num < settings.pages and not (
                        incremental
                        and consecutive_empty_pages
                        >= settings.incremental_stop_empty_pages
                    ):
                        time.sleep(settings.page_delay_sec)

                if query and query_idx < total_queries:
                    time.sleep(settings.page_delay_sec)

            listings: list[dict[str, Any]] = []
            preview_list = list(all_previews.values())
            new_previews = [p for p in preview_list if p.autoplius_id not in known_ids]

            if settings.enrich_details:
                if settings.enrich_new_only and incremental and not target_mode:
                    to_enrich = [
                        p
                        for p in preview_list
                        if p.autoplius_id not in detail_scraped_ids
                    ]
                else:
                    limit = (
                        settings.enrich_limit
                        if settings.enrich_limit > 0
                        else len(preview_list)
                    )
                    to_enrich = preview_list[:limit]

                enrich_ids = {p.autoplius_id for p in to_enrich}
                skip = [p for p in preview_list if p.autoplius_id not in enrich_ids]

                logger.info(
                    "Enriching %s/%s listing detail pages (delay=%ss, new_only=%s)",
                    len(to_enrich),
                    len(preview_list),
                    settings.detail_delay_sec,
                    settings.enrich_new_only and incremental,
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
                        listings.append(
                            merge_preview_and_detail(
                                preview, detail=detail, settings=settings
                            )
                        )
                        detail_ok += 1
                    except Exception as exc:
                        detail_fail += 1
                        logger.warning(
                            "Detail failed for %s: %s", preview.autoplius_id, exc
                        )
                        listings.append(
                            merge_preview_and_detail(
                                preview, error=str(exc)[:300], settings=settings
                            )
                        )

                for preview in skip:
                    listings.append(merge_preview_and_detail(preview, settings=settings))
            else:
                listings = [
                    merge_preview_and_detail(p, settings=settings) for p in preview_list
                ]
        finally:
            browser_or_context.close()

    finished_at = datetime.now(timezone.utc)
    current_ids = {item["autoplius_id"] for item in listings}
    diff = diff_stats(current_ids, previous_ids)
    removed_listing_ids = sorted(previous_ids - current_ids)

    payload: dict[str, Any] = {
        "mode": "target" if target_mode else ("test" if settings.test_mode else "prod"),
        "scrape_mode": "target" if target_mode else ("incremental" if incremental else "full"),
        "scrape_mode_reason": mode_reason,
        "target_queries": [q.label for q in queries] if queries else None,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_sec": round((finished_at - started_at).total_seconds(), 2),
        "pages_scraped": pages_scraped,
        "listing_count": len(listings),
        "new_listings_found": len(new_previews),
        "details_scraped": detail_ok,
        "details_failed": detail_fail,
        "enrich_details": settings.enrich_details,
        "enrich_new_only": settings.enrich_new_only and incremental and not target_mode,
        "page_stats": page_stats,
        "diff_vs_previous": diff,
        "removed_listing_ids": removed_listing_ids,
        "archive_removed": archive_removed,
        "listings": listings,
    }

    snapshot_path = save_snapshot(
        payload,
        data_dir=settings.data_dir,
        test_mode=settings.test_mode,
        update_latest=update_latest_snapshot,
    )
    run_id, archived_count = save_payload_to_db(
        settings.db_path,
        payload,
        snapshot_path=str(snapshot_path),
    )

    photo_sync = sync_run_photos(settings, listings)
    payload["photo_sync"] = photo_sync

    logger.info(
        "Done (%s): %s listings (%s new vs DB), details ok=%s fail=%s | "
        "new=%s removed=%s unchanged=%s archived=%s | db_run_id=%s | photos uploaded=%s",
        payload["scrape_mode"],
        len(listings),
        len(new_previews),
        detail_ok,
        detail_fail,
        diff["new"],
        diff["removed"],
        diff["unchanged"],
        archived_count,
        run_id,
        photo_sync.get("uploaded", 0),
    )
    return ScrapeRunResult(payload=payload, snapshot_path=str(snapshot_path), diff=diff)


def run_job(settings: Settings) -> ScrapeRunResult:
    incremental, _ = resolve_scrape_mode(settings)
    logger.info(
        "Starting scrape (test_mode=%s, pages=%s, enrich=%s, auto_captcha=%s, incremental=%s)",
        settings.test_mode,
        settings.pages,
        settings.enrich_details,
        settings.auto_captcha,
        incremental,
    )
    try:
        return scrape_search_pages(settings)
    except CaptchaError as exc:
        logger.error("Captcha error: %s", exc)
        raise
    except Exception:
        logger.exception("Scrape failed")
        raise
