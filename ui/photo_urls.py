from __future__ import annotations

from urllib.parse import quote, urlparse

_ALLOWED_PHOTO_SUFFIXES = (".autoplius.lt",)
_ALLOWED_PHOTO_MARKERS = ("autoplius-img",)


def is_external_photo_url(url: str | None) -> bool:
    if not url or url.startswith("/"):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if any(host == suffix[1:] or host.endswith(suffix) for suffix in _ALLOWED_PHOTO_SUFFIXES):
        return True
    return any(marker in host for marker in _ALLOWED_PHOTO_MARKERS)


def photo_display_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("/media/"):
        return url
    if is_external_photo_url(url):
        return f"/media/proxy?url={quote(url, safe='')}"
    return url


def photo_display_urls(urls: list[str] | None) -> list[str]:
    result: list[str] = []
    for raw in urls or []:
        if not raw:
            continue
        display = photo_display_url(raw)
        if display:
            result.append(display)
    return result
