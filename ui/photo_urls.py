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


def _with_width(url: str, width: int | None) -> str:
    if not width:
        return url
    query = url.split("?", 1)[1] if "?" in url else ""
    if any(part.startswith("w=") for part in query.split("&") if part):
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}w={int(width)}"


def photo_display_url(url: str | None, *, width: int | None = None) -> str | None:
    if not url:
        return None
    if url.startswith("/media/"):
        return _with_width(url, width)
    if is_external_photo_url(url):
        return _with_width(f"/media/proxy?url={quote(url, safe='')}", width)
    return url


def photo_display_urls(urls: list[str] | None, *, width: int | None = None) -> list[str]:
    result: list[str] = []
    for raw in urls or []:
        if not raw:
            continue
        display = photo_display_url(raw, width=width)
        if display:
            result.append(display)
    return result
