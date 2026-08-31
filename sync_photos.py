#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import logging
import mimetypes
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import Settings
from scraper.db import fetch_all_listings, update_listing_photos
from scraper.s3_storage import (
    build_media_url,
    ensure_bucket_exists,
    is_media_url,
    object_exists,
    put_object,
    storage_key_from_media_url,
)

logger = logging.getLogger(__name__)


def _collect_source_urls(item: dict) -> list[str]:
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


def _existing_media_keys(item: dict) -> list[str]:
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
    item: dict,
    *,
    timeout: int,
    dry_run: bool,
    force: bool,
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

    for index, source_url in enumerate(source_urls):
        try:
            payload, content_type_header = _download_image(source_url, timeout=timeout)
        except Exception as exc:
            return "error_download", uploaded, f"{source_url}: {exc}"

        if not payload:
            return "error_empty", uploaded, source_url

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
            return "error_upload", uploaded, f"{storage_key}: {exc}"

        media_urls.append(build_media_url(storage_key))
        uploaded += 1

    if dry_run:
        return "would_sync", uploaded, ""

    update_listing_photos(
        settings.db_path,
        listing_id,
        photo_url=media_urls[0] if media_urls else None,
        photo_urls=media_urls,
    )
    return "synced", uploaded, ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Download listing photos and upload to MinIO/S3")
    parser.add_argument("--limit", type=int, default=0, help="Limit listings (0 = all)")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout for image download")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload or update DB")
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing objects")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings.from_env()
    if not settings.s3_enabled:
        raise SystemExit("S3 is not configured. Set S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY in .env")

    if not settings.db_path.is_file():
        raise SystemExit(f"Database not found: {settings.db_path}")

    ensure_bucket_exists(settings)
    listings = fetch_all_listings(settings.db_path)
    if args.limit and args.limit > 0:
        listings = listings[: args.limit]

    stats: dict[str, int] = {}
    total_uploaded = 0

    for idx, item in enumerate(listings, start=1):
        status, uploaded, detail = sync_listing_photos(
            settings,
            item,
            timeout=args.timeout,
            dry_run=args.dry_run,
            force=args.force,
        )
        stats[status] = stats.get(status, 0) + 1
        total_uploaded += uploaded
        suffix = f" ({detail})" if detail else ""
        logger.info(
            "[%s/%s] #%s %s -> %s photos=%s%s",
            idx,
            len(listings),
            item.get("autoplius_id"),
            (item.get("title") or "")[:50],
            status,
            uploaded,
            suffix,
        )

    logger.info(
        "sync-summary: %s total_listings=%s uploaded_or_planned=%s dry_run=%s force=%s",
        " ".join(f"{key}={value}" for key, value in sorted(stats.items())),
        len(listings),
        total_uploaded,
        args.dry_run,
        args.force,
    )


if __name__ == "__main__":
    main()
