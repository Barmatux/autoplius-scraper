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
from autoplius.photo_urls import normalize_photo_list
from autoplius.search_query import SearchQuery
from autoplius.translate import translate_to_russian
from autoplius.urls import build_search_url, configure_base_url

from scraper.config import Settings
from scraper.db import (
    fetch_listings_pending_detail,
    hours_since_last_full_scrape,
    load_detail_scraped_ids,
    load_known_ids,
    save_payload_to_db,
    upsert_listing_item,
)
from scraper.photo_sync import sync_run_photos
from scraper.storage import diff_stats, load_latest_ids, save_snapshot

logger = logging.getLogger(__name__)


@dataclass
class ScrapeRunResult:
    payload: dict[str, Any]
    snapshot_path: str
    diff: dict[str, int]


def listing_to_preview(item: dict[str, Any]) -> SearchListingPreview:
    return SearchListingPreview(
        autoplius_id=int(item["autoplius_id"]),
        url=item.get("url") or "",
        title=item.get("title") or "",
        year=item.get("year"),
        body_type=item.get("body_type"),
        price_eur=item.get("price_eur"),
        price_net_eur=item.get("price_net_eur"),
        price_gross_eur=item.get("price_gross_eur"),
        price_vat_note=item.get("price_vat_note"),
        fuel=item.get("fuel"),
        transmission=item.get("transmission"),
        engine=item.get("engine"),
        mileage_km=item.get("mileage_km"),
        city=item.get("city"),
        photo_url=item.get("photo_url"),
        has_vin_badge=bool(item.get("has_vin_badge")),
    )


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
        detail_photos = normalize_photo_list(detail.get("photo_urls") or [])
        if detail_photos:
            row["photo_urls"] = detail_photos
            row["photo_url"] = detail_photos[0]
        elif row.get("photo_url"):
            row["photo_urls"] = normalize_photo_list([row["photo_url"]])
        else:
            row["photo_urls"] = []
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
    enrich_only: bool = False,
) -> ScrapeRunResult:
    started_at = datetime.now(timezone.utc)
    previous_ids = load_latest_ids(settings.data_dir) if update_latest_snapshot else set()
    known_ids = load_known_ids(settings.db_path)
    detail_scraped_ids = load_detail_scraped_ids(settings.db_path)
    target_mode = bool(queries) or enrich_only
    if target_mode and not enrich_only:
        incremental = False
        mode_reason = f"target batch ({len(queries)} queries)"
        paginate_until_empty = True
        if archive_removed is None:
            archive_removed = False
        update_latest_snapshot = False
    elif enrich_only:
        incremental = False
        mode_reason = "target enrich-only resume"
        paginate_until_empty = False
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
            if enrich_only:
                pending = fetch_listings_pending_detail(settings.db_path)
                for item in pending:
                    preview = listing_to_preview(item)
                    all_previews[preview.autoplius_id] = preview
                logger.info(
                    "Enrich-only resume: %s listings pending detail scrape",
                    len(all_previews),
                )

            for query_idx, query in enumerate(query_plan, start=1):
                if enrich_only:
                    break
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
                    if query is not None:
                        url = query.build_url(page=page_num, base_url=settings.autoplius_base_url)
                    else:
                        url = build_search_url(page=page_num, newest_first=newest_first)
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
                    new_for_query = 0
                    for preview in previews:
                        is_new = preview.autoplius_id not in known_ids
                        if preview.autoplius_id not in query_previews:
                            new_for_query += 1
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
                            "new_for_query": new_for_query,
                        }
                    )
                    logger.info(
                        "Page %s (%s): %s listings (%s new vs DB, %s new for query, query total %s, run total %s)",
                        page_num,
                        query.label if query else "default",
                        len(previews),
                        new_on_page,
                        new_for_query,
                        len(query_previews),
                        len(all_previews),
                    )

                    stop_after_no_new = settings.incremental_stop_empty_pages
                    if incremental:
                        no_new = new_on_page == 0
                    elif target_mode or paginate_until_empty:
                        no_new = new_for_query == 0
                    else:
                        no_new = False

                    if no_new:
                        consecutive_empty_pages += 1
                        if consecutive_empty_pages >= stop_after_no_new:
                            logger.info(
                                "Stopping pagination after %s page(s) with no new listings (%s)",
                                consecutive_empty_pages,
                                query.label if query else "default",
                            )
                            break
                    else:
                        consecutive_empty_pages = 0

                    if page_num < settings.pages and consecutive_empty_pages < stop_after_no_new:
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
                elif target_mode or enrich_only:
                    to_enrich = [
                        p
                        for p in preview_list
                        if p.autoplius_id not in detail_scraped_ids
                    ]
                    if settings.enrich_limit > 0:
                        to_enrich = to_enrich[: settings.enrich_limit]
                else:
                    limit = (
                        settings.enrich_limit
                        if settings.enrich_limit > 0
                        else len(preview_list)
                    )
                    to_enrich = preview_list[:limit]

                if target_mode and preview_list and not enrich_only:
                    checkpoint_at = datetime.now(timezone.utc).isoformat()
                    for preview in preview_list:
                        upsert_listing_item(
                            settings.db_path,
                            merge_preview_and_detail(preview, settings=settings),
                            seen_at=checkpoint_at,
                        )
                    logger.info(
                        "Saved %s target search previews to DB before enrichment",
                        len(preview_list),
                    )
                    detail_scraped_ids = load_detail_scraped_ids(settings.db_path)
                    to_enrich = [
                        p
                        for p in preview_list
                        if p.autoplius_id not in detail_scraped_ids
                    ]
                    if settings.enrich_limit > 0:
                        to_enrich = to_enrich[: settings.enrich_limit]

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
                        if target_mode or enrich_only:
                            upsert_listing_item(
                                settings.db_path,
                                listings[-1],
                                seen_at=datetime.now(timezone.utc).isoformat(),
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
                        if target_mode or enrich_only:
                            upsert_listing_item(
                                settings.db_path,
                                listings[-1],
                                seen_at=datetime.now(timezone.utc).isoformat(),
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
        "scrape_mode": (
            "target_resume"
            if enrich_only
            else ("target" if target_mode else ("incremental" if incremental else "full"))
        ),
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

    try:
        from autoplius.engine_catalog import refresh_engine_catalog

        refresh_engine_catalog(settings.db_path)
    except Exception:
        logger.exception("Engine catalog refresh failed")

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
