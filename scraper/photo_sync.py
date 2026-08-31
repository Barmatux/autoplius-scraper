from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scraper.config import Settings
from scraper.db import update_listing_photos
from scraper.s3_storage import (
    build_media_url,
    ensure_bucket_exists,
    is_media_url,
    object_exists,
    put_object,
    storage_key_from_media_url,
)

logger = logging.getLogger(__name__)


def _collect_source_urls(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in item.get("photo_urls") or []:
        if not raw or raw in seen:
            continue
        if is_media_url(raw):
            continue
        seen.add(raw)
        urls.append(raw)
    photo_url = item.get("photo_url")
    if photo_url and not is_media_url(photo_url) and photo_url not in seen:
        urls.insert(0, photo_url)
    return urls


def _guess_ext_and_content_type(url: str, content_type_header: str | None) -> tuple[str, str]:
    content_type = (content_type_header or "").split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        ext = mimetypes.guess_extension(content_type) or ".jpg"
        return ext, content_type

    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in {".jpg", ".jpeg"}:
        return ".jpg", "image/jpeg"
    if path_ext == ".png":
        return ".png", "image/png"
    if path_ext == ".webp":
        return ".webp", "image/webp"
    return ".jpg", "image/jpeg"


def _download_image(url: str, timeout: int) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutopliusScraper/1.0)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://autoplius.lt/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
    return data, content_type


def _build_storage_key(listing_id: int, source_url: str, index: int, ext: str) -> str:
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
    return f"listings/{listing_id}/{index:03d}_{digest}{ext}"


def _existing_media_keys(item: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for raw in item.get("photo_urls") or []:
        key = storage_key_from_media_url(raw) if is_media_url(raw) else None
        if key:
            keys.append(key)
    if item.get("photo_url"):
        key = storage_key_from_media_url(item["photo_url"])
        if key and key not in keys:
            keys.insert(0, key)
    return keys


def sync_listing_photos(
    settings: Settings,
    item: dict[str, Any],
    *,
    timeout: int,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[str, int, str]:
    listing_id = int(item["autoplius_id"])
    source_urls = _collect_source_urls(item)
    if not source_urls:
        existing = _existing_media_keys(item)
        if existing:
            return "skip_already_synced", len(existing), ""
        return "skip_no_photos", 0, ""

    if not force:
        existing = _existing_media_keys(item)
        if existing and len(existing) >= len(source_urls):
            return "skip_already_synced", len(existing), ""

    media_urls: list[str] = []
    uploaded = 0
    errors: list[str] = []

    for index, source_url in enumerate(source_urls):
        try:
            payload, content_type_header = _download_image(source_url, timeout=timeout)
        except Exception as exc:
            errors.append(f"{source_url}: {exc}")
            continue

        if not payload:
            errors.append(f"{source_url}: empty")
            continue

        ext, content_type = _guess_ext_and_content_type(source_url, content_type_header)
        storage_key = _build_storage_key(listing_id, source_url, index, ext)

        if not force and object_exists(settings, storage_key):
            media_urls.append(build_media_url(storage_key))
            continue

        if dry_run:
            media_urls.append(build_media_url(storage_key))
            uploaded += 1
            continue

        try:
            put_object(
                settings,
                storage_key=storage_key,
                body=payload,
                content_type=content_type,
            )
        except Exception as exc:
            errors.append(f"{storage_key}: {exc}")
            continue

        media_urls.append(build_media_url(storage_key))
        uploaded += 1

    if dry_run:
        if media_urls:
            return "would_sync", uploaded, "; ".join(errors[:2])
        return "error_download", uploaded, errors[0] if errors else "no photos"

    if not media_urls:
        if errors:
            return "error_download", uploaded, errors[0]
        return "skip_no_photos", 0, ""

    update_listing_photos(
        settings.db_path,
        listing_id,
        photo_url=media_urls[0] if media_urls else None,
        photo_urls=media_urls,
    )
    if errors:
        return "synced_partial", uploaded, errors[0]
    return "synced", uploaded, ""


def sync_listings_photos(
    settings: Settings,
    listings: list[dict[str, Any]],
    *,
    timeout: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    log_each: bool = False,
) -> dict[str, Any]:
    if not settings.s3_enabled:
        return {"enabled": False, "reason": "s3_not_configured", "listings": len(listings)}

    timeout = timeout if timeout is not None else settings.sync_photos_timeout_sec
    ensure_bucket_exists(settings)

    stats: dict[str, int] = {}
    total_uploaded = 0

    for idx, item in enumerate(listings, start=1):
        status, uploaded, detail = sync_listing_photos(
            settings,
            item,
            timeout=timeout,
            dry_run=dry_run,
            force=force,
        )
        stats[status] = stats.get(status, 0) + 1
        total_uploaded += uploaded
        if log_each:
            suffix = f" ({detail})" if detail else ""
            logger.info(
                "[photos %s/%s] #%s %s -> %s uploaded=%s%s",
                idx,
                len(listings),
                item.get("autoplius_id"),
                (item.get("title") or "")[:50],
                status,
                uploaded,
                suffix,
            )

    return {
        "enabled": True,
        "listings": len(listings),
        "uploaded": total_uploaded,
        "stats": stats,
        "dry_run": dry_run,
        "force": force,
    }


def sync_run_photos(settings: Settings, listings: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.sync_photos_after_scrape:
        return {"enabled": False, "reason": "disabled", "listings": len(listings)}

    logger.info("Syncing photos for %s listings from current run", len(listings))
    result = sync_listings_photos(settings, listings, log_each=False)
    if result.get("enabled"):
        logger.info(
            "Photo sync done: listings=%s uploaded=%s stats=%s",
            result["listings"],
            result["uploaded"],
            result["stats"],
        )
    return result
