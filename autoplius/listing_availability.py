"""Probe whether a listing URL is still live on Autoplius."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from autoplius.browser import is_challenge_page, is_not_found_page
from autoplius.urls import get_base_url

logger = logging.getLogger(__name__)

LiveStatus = Literal["available", "unavailable", "unknown"]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_CACHE_TTL_SEC = float(os.environ.get("LISTING_LIVE_CACHE_SEC", "1200") or "1200")
_HTTP_TIMEOUT_SEC = float(os.environ.get("LISTING_LIVE_HTTP_TIMEOUT_SEC", "10") or "10")
_BROWSER_TIMEOUT_MS = int(float(os.environ.get("LISTING_LIVE_BROWSER_TIMEOUT_SEC", "20") or "20") * 1000)

_cache: dict[str, tuple[float, LiveStatus]] = {}
_cache_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_inflight_lock = threading.Lock()


def _normalize_url(url: str) -> str:
    return (url or "").strip()


def _cache_get(url: str) -> LiveStatus | None:
    with _cache_lock:
        hit = _cache.get(url)
        if not hit:
            return None
        expires_at, status = hit
        if expires_at < time.monotonic():
            _cache.pop(url, None)
            return None
        return status


def _cache_set(url: str, status: LiveStatus) -> LiveStatus:
    with _cache_lock:
        _cache[url] = (time.monotonic() + max(30.0, _CACHE_TTL_SEC), status)
    return status


def classify_listing_html(*, status_code: int, url: str, title: str, html: str) -> LiveStatus:
    """Classify an Autoplius response without performing network I/O."""
    final_url = (url or "").lower()
    if status_code == 404 or status_code == 410:
        return "unavailable"
    if status_code >= 500:
        return "unknown"
    if is_not_found_page(title, html):
        return "unavailable"
    if "/404" in final_url or final_url.rstrip("/").endswith("/not-found"):
        return "unavailable"
    if is_challenge_page(html, title):
        return "unknown"
    if status_code in {401, 403, 429}:
        return "unknown"
    if status_code == 200 and _looks_like_listing(html):
        return "available"
    if status_code == 200:
        return "unknown"
    return "unknown"


def _looks_like_listing(html: str) -> bool:
    blob = html.lower()
    markers = (
        "second-parameters",
        "parameter-row",
        "announcement-price",
        "announcement-title",
        "js-seller-phone",
        "data-clipboard",
        "/objavlenija/",
        "/skelbimai/",
    )
    hits = sum(1 for marker in markers if marker in blob)
    return hits >= 2 or ("parameter-row" in blob and "€" in html)


def probe_listing_http(url: str, *, timeout: float | None = None) -> LiveStatus:
    target = _normalize_url(url)
    if not target:
        return "unknown"
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "unknown"

    request = Request(
        target,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Referer": f"{get_base_url()}/",
        },
    )
    wait = _HTTP_TIMEOUT_SEC if timeout is None else timeout
    try:
        with urlopen(request, timeout=wait) as response:
            raw = response.read(400_000)
            status_code = int(getattr(response, "status", 200) or 200)
            final_url = response.geturl() or target
            content_type = (response.headers.get("Content-Type") or "").lower()
    except HTTPError as exc:
        raw = exc.read(400_000) if hasattr(exc, "read") else b""
        status_code = int(exc.code or 0)
        final_url = target
        content_type = ""
    except (URLError, TimeoutError, OSError) as exc:
        logger.info("listing live HTTP probe failed for %s: %s", target, exc)
        return "unknown"

    if "text/html" not in content_type and raw[:1] not in (b"<", b"!"):
        # Unexpected payload (often CF binary/block); treat as unknown.
        if status_code == 200:
            return "unknown"

    html = raw.decode("utf-8", errors="replace")
    title = _extract_title(html)
    return classify_listing_html(
        status_code=status_code,
        url=final_url,
        title=title,
        html=html,
    )


def _extract_title(html: str) -> str:
    lower = html.lower()
    start = lower.find("<title")
    if start < 0:
        return ""
    start = lower.find(">", start)
    if start < 0:
        return ""
    end = lower.find("</title>", start)
    if end < 0:
        return ""
    return html[start + 1 : end].strip()


def _profile_dir() -> Path | None:
    raw = os.environ.get("PROFILE_DIR", "").strip()
    if raw:
        path = Path(raw)
        return path if path.is_dir() else None
    default = Path("/var/lib/autoplius-scraper/browser-profile")
    if default.is_dir():
        return default
    local = Path(".browser-profile")
    return local if local.is_dir() else None


def _browser_enabled() -> bool:
    mode = (os.environ.get("LISTING_LIVE_BROWSER") or "auto").strip().lower()
    if mode in {"0", "false", "no", "off", "http"}:
        return False
    if mode in {"1", "true", "yes", "on", "browser", "playwright"}:
        return True
    return _profile_dir() is not None


def probe_listing_browser(url: str) -> LiveStatus:
    target = _normalize_url(url)
    if not target:
        return "unknown"
    try:
        from playwright.sync_api import sync_playwright

        from autoplius.browser import create_browser_context
    except Exception as exc:
        logger.info("listing live browser unavailable: %s", exc)
        return "unknown"

    profile = _profile_dir()
    try:
        with sync_playwright() as playwright:
            context = create_browser_context(
                playwright,
                headless=True,
                profile_dir=profile,
                storage_state=None,
            )
            page = context.new_page()
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=_BROWSER_TIMEOUT_MS)
                page.wait_for_timeout(800)
                title = page.title() or ""
                html = page.content()
                final_url = page.url or target
                if is_not_found_page(title, html):
                    return "unavailable"
                if is_challenge_page(html, title):
                    return "unknown"
                from autoplius.browser import has_target_content

                if has_target_content(page, html) or _looks_like_listing(html):
                    return "available"
                return classify_listing_html(
                    status_code=200,
                    url=final_url,
                    title=title,
                    html=html,
                )
            finally:
                context.close()
    except Exception as exc:
        logger.info("listing live browser probe failed for %s: %s", target, exc)
        return "unknown"


def probe_listing_url(url: str) -> LiveStatus:
    """Return live status for a listing URL (cached)."""
    target = _normalize_url(url)
    if not target:
        return "unknown"

    cached = _cache_get(target)
    if cached is not None:
        return cached

    with _inflight_lock:
        event = _inflight.get(target)
        leader = event is None
        if leader:
            event = threading.Event()
            _inflight[target] = event
    if not leader:
        event.wait(timeout=max(_HTTP_TIMEOUT_SEC, 25.0) + 5.0)
        return _cache_get(target) or "unknown"

    try:
        status = probe_listing_http(target)
        if status == "unknown" and _browser_enabled():
            status = probe_listing_browser(target)
        return _cache_set(target, status)
    finally:
        with _inflight_lock:
            _inflight.pop(target, None)
        event.set()
