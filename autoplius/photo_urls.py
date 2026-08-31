from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

AUTOPLIUS_IMG_HOST = "autoplius-img"
# Autoplius CDN path prefixes: ann_2_=full, ann_3_=medium, ann_25_=small preview.
FULL_SIZE_PREFIX = "ann_2_"
MEDIUM_SIZE_PREFIX = "ann_3_"
THUMB_SIZE_PREFIX = "ann_25_"
_SIZE_PREFIX_RE = re.compile(r"(https://autoplius-img\.dgn\.lt/)ann_\d+_", re.I)
_ASSET_KEY_RE = re.compile(r"ann_\d+_(.+)$", re.I)


def is_autoplius_cdn_url(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return AUTOPLIUS_IMG_HOST in host


def is_media_proxy_url(url: str | None) -> bool:
    return bool(url and url.startswith("/media/object?key="))


def photo_asset_key(url: str) -> str:
    """Stable dedupe key for the same logical photo across size variants."""
    match = _ASSET_KEY_RE.search(url)
    if match:
        return match.group(1).casefold()
    return url.casefold()


def best_photo_url(url: str | None) -> str | None:
    """Return full-size Autoplius CDN URL (ann_2_) when possible."""
    if not url:
        return None
    clean = url.strip().split()[0]
    if not clean:
        return None
    if is_media_proxy_url(clean) or not is_autoplius_cdn_url(clean):
        return clean
    return _SIZE_PREFIX_RE.sub(rf"\1{FULL_SIZE_PREFIX}", clean, count=1)


def thumb_photo_url(url: str | None) -> str | None:
    """Small preview for list cards and thumbnail strip."""
    if not url:
        return None
    clean = url.strip().split()[0]
    if not clean:
        return None
    if is_media_proxy_url(clean):
        return clean
    if not is_autoplius_cdn_url(clean):
        return clean
    return _SIZE_PREFIX_RE.sub(rf"\1{THUMB_SIZE_PREFIX}", clean, count=1)


def normalize_photo_list(urls: Iterable[str] | None) -> list[str]:
    """Dedupe photos and keep the best available URL per asset."""
    ordered: list[tuple[int, str]] = []
    index_by_key: dict[str, int] = {}
    for raw in urls or []:
        full = best_photo_url(raw)
        if not full:
            continue
        key = photo_asset_key(full)
        if key in index_by_key:
            continue
        index_by_key[key] = len(ordered)
        ordered.append((len(ordered), full))
    return [url for _, url in sorted(ordered, key=lambda item: item[0])]


def listing_photo_sets(urls: Iterable[str] | None) -> dict[str, list[str] | str | None]:
    full = normalize_photo_list(urls)
    thumbs = [thumb for url in full if (thumb := thumb_photo_url(url))]
    return {
        "full": full,
        "thumb": thumbs,
        "cover_full": full[0] if full else None,
        "cover_thumb": thumbs[0] if thumbs else None,
    }
