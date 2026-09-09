"""Nightly reconcile: deep search (A) + live-probe archive (B)."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scraper.config import Settings
from scraper.db import (
    archive_listings_by_ids,
    fetch_stale_active_listings_for_probe,
    touch_listing_last_seen,
)
from scraper.job import scrape_search_pages

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def run_nightly_deep_search(settings: Settings) -> dict[str, Any]:
    """A: paginate default search until empty; archive missing with safety gates."""
    max_pages = max(50, _env_int("NIGHTLY_MAX_PAGES", 500))
    page_delay = _env_float("NIGHTLY_PAGE_DELAY_SEC", max(settings.page_delay_sec, 4.0))
    nightly_settings = replace(
        settings,
        pages=max_pages,
        page_delay_sec=page_delay,
        incremental_scrape=False,
        enrich_details=_env_bool("NIGHTLY_ENRICH_DETAILS", False),
        enrich_new_only=True,
        search_newest_first=False,
        sync_photos_after_scrape=_env_bool("NIGHTLY_SYNC_PHOTOS", False),
    )
    logger.info(
        "Nightly A start: max_pages=%s page_delay=%s enrich=%s",
        nightly_settings.pages,
        nightly_settings.page_delay_sec,
        nightly_settings.enrich_details,
    )
    result = scrape_search_pages(nightly_settings, nightly=True)
    payload = result.payload
    summary = {
        "phase": "deep_search",
        "scrape_mode": payload.get("scrape_mode"),
        "pages_scraped": payload.get("pages_scraped"),
        "listing_count": payload.get("listing_count"),
        "diff": payload.get("diff_vs_previous"),
        "archived_snapshot": payload.get("diff_vs_previous", {}).get("removed")
        if isinstance(payload.get("diff_vs_previous"), dict)
        else None,
        "archived_missing_from_search": payload.get("archived_missing_from_search", 0),
        "archived_total": payload.get("archived_total"),
        "snapshot_path": result.snapshot_path,
        "duration_sec": payload.get("duration_sec"),
    }
    logger.info("Nightly A done: %s", summary)
    return summary


def run_nightly_live_probe(settings: Settings) -> dict[str, Any]:
    """B: probe stale active URLs; archive only confirmed unavailable."""
    from autoplius.listing_availability import probe_listing_result

    older_h = _env_float("NIGHTLY_STALE_HOURS", 36.0)
    limit = max(0, _env_int("NIGHTLY_PROBE_LIMIT", 250))
    delay = max(0.5, _env_float("NIGHTLY_PROBE_DELAY_SEC", 2.5))
    max_unknown_streak = max(5, _env_int("NIGHTLY_PROBE_MAX_UNKNOWN_STREAK", 25))

    candidates = fetch_stale_active_listings_for_probe(
        settings.db_path,
        older_than_hours=older_h,
        limit=limit,
    )
    stats = {
        "phase": "live_probe",
        "candidates": len(candidates),
        "older_than_hours": older_h,
        "limit": limit,
        "available": 0,
        "unavailable": 0,
        "unknown": 0,
        "archived": 0,
        "touched_available": 0,
        "stopped_early": None,
    }
    logger.info(
        "Nightly B start: candidates=%s stale_hours=%s delay=%s",
        len(candidates),
        older_h,
        delay,
    )
    unknown_streak = 0
    to_archive: list[int] = []
    now = datetime.now(timezone.utc).isoformat()

    for index, item in enumerate(candidates, start=1):
        listing_id = int(item["autoplius_id"])
        url = (item.get("url") or "").strip()
        if not url:
            stats["unknown"] += 1
            continue
        result = probe_listing_result(url, listing_id=listing_id)
        if result.status == "unavailable":
            stats["unavailable"] += 1
            to_archive.append(listing_id)
            unknown_streak = 0
        elif result.status == "available":
            stats["available"] += 1
            touch_listing_last_seen(settings.db_path, listing_id, seen_at=now)
            stats["touched_available"] += 1
            unknown_streak = 0
        else:
            stats["unknown"] += 1
            unknown_streak += 1
            if unknown_streak >= max_unknown_streak:
                stats["stopped_early"] = (
                    f"too many unknown probes in a row ({unknown_streak}); "
                    "likely Cloudflare — aborting probe phase"
                )
                logger.warning("%s", stats["stopped_early"])
                break

        if index < len(candidates):
            time.sleep(delay)

    if to_archive:
        stats["archived"] = archive_listings_by_ids(settings.db_path, to_archive, archived_at=now)

    logger.info("Nightly B done: %s", stats)
    return stats


def write_nightly_summary(logs_dir: Path, summary: dict[str, Any]) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "nightly-reconcile.jsonl"
    line = json.dumps(summary, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return path


def run_nightly_reconcile(
    settings: Settings,
    *,
    skip_deep_search: bool = False,
    skip_probe: bool = False,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    summary: dict[str, Any] = {
        "started_at": started.isoformat(),
        "phases": {},
    }
    try:
        if not skip_deep_search and _env_bool("NIGHTLY_DEEP_SEARCH", True):
            summary["phases"]["A"] = run_nightly_deep_search(settings)
        else:
            summary["phases"]["A"] = {"skipped": True}

        if not skip_probe and _env_bool("NIGHTLY_LIVE_PROBE", True):
            summary["phases"]["B"] = run_nightly_live_probe(settings)
            try:
                from ui.page_cache import invalidate_page_cache

                invalidate_page_cache()
            except ImportError:
                pass
        else:
            summary["phases"]["B"] = {"skipped": True}

        summary["ok"] = True
    except Exception as exc:
        logger.exception("Nightly reconcile failed")
        summary["ok"] = False
        summary["error"] = str(exc)
        raise
    finally:
        finished = datetime.now(timezone.utc)
        summary["finished_at"] = finished.isoformat()
        summary["duration_sec"] = round((finished - started).total_seconds(), 2)
        out = write_nightly_summary(settings.logs_dir, summary)
        summary["summary_path"] = str(out)
        logger.info("Nightly reconcile summary written to %s", out)
    return summary
