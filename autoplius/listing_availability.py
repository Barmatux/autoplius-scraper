"""Probe whether a listing URL is still live on Autoplius."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
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

_INACTIVE_LISTING_RE = re.compile(
    r"skelbimas\s+nerastas|"
    r"skelbimas\s+neaktyvus|"
    r"объявление\s+не\s+найдено|"
    r"объявление\s+неактивно|"
    r"advertisement\s+(?:was\s+)?not\s+found|"
    r"this\s+(?:advertisement|listing)\s+is\s+(?:no\s+longer\s+available|unavailable|inactive)|"
    r"announcement\s+not\s+found|"
    r"page\s+not\s+found|"
    r"страница\s+не\s+найдена",
    re.I,
)

_CACHE_TTL_SEC = float(os.environ.get("LISTING_LIVE_CACHE_SEC", "1200") or "1200")
_UNKNOWN_CACHE_TTL_SEC = float(os.environ.get("LISTING_LIVE_UNKNOWN_CACHE_SEC", "90") or "90")
_HTTP_TIMEOUT_SEC = float(os.environ.get("LISTING_LIVE_HTTP_TIMEOUT_SEC", "10") or "10")
_BROWSER_TIMEOUT_MS = int(float(os.environ.get("LISTING_LIVE_BROWSER_TIMEOUT_SEC", "25") or "25") * 1000)
_PROBE_TIMEOUT_SEC = float(os.environ.get("LISTING_LIVE_PROBE_TIMEOUT_SEC", "35") or "35")

_cache: dict[str, tuple[float, LiveStatus]] = {}
_cache_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="listing-live")
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
    ttl = _UNKNOWN_CACHE_TTL_SEC if status == "unknown" else _CACHE_TTL_SEC
    with _cache_lock:
        _cache[url] = (time.monotonic() + max(15.0, ttl), status)
    return status


def classify_listing_html(
    *,
    status_code: int,
    url: str,
    title: str,
    html: str,
    listing_id: int | None = None,
) -> LiveStatus:
    """Classify an Autoplius response without performing network I/O."""
    final_url = (url or "").lower()
    if status_code == 404 or status_code == 410:
        return "unavailable"
    if status_code >= 500:
        return "unknown"
    if is_not_found_page(title, html) or _is_inactive_listing(title, html):
        return "unavailable"
    if "/404" in final_url or final_url.rstrip("/").endswith("/not-found"):
        return "unavailable"
    if is_challenge_page(html, title):
        return "unknown"
    if status_code in {401, 403, 429}:
        return "unknown"
    if status_code == 200 and _looks_like_active_listing(html, listing_id=listing_id):
        return "available"
    if status_code == 200:
        return "unknown"
    return "unknown"


def _is_inactive_listing(title: str, html: str) -> bool:
    blob = f"{title}\n{html}"
    return bool(_INACTIVE_LISTING_RE.search(blob))


def _looks_like_active_listing(html: str, *, listing_id: int | None = None) -> bool:
    """Require detail-page markers; ignore search/404 pages with related ads."""
    blob = html.lower()
    if "second-parameters" not in blob or "parameter-row" not in blob:
        return False
    # Related-ads / 404 shells often still contain /objavlenija/ links — never
    # treat those alone as proof that *this* listing is live.
    detail_markers = (
        "announcement-price",
        "js-seller-phone",
        "contacts-phone",
        "seller-contact",
        "announcement-title",
        "bookmarked-announcement",
    )
    if not any(marker in blob for marker in detail_markers):
        return False
    if listing_id is None:
        return True
    sid = str(listing_id)
    # Require the id as its own token so related ads with nearby ids don't match.
    return bool(re.search(rf"(?<!\d){re.escape(sid)}(?!\d)", html))


def probe_listing_http(
    url: str,
    *,
    timeout: float | None = None,
    listing_id: int | None = None,
) -> LiveStatus:
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
        listing_id=listing_id,
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
    if _profile_dir() is not None:
        return True
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def probe_listing_browser(url: str, *, listing_id: int | None = None) -> LiveStatus:
    target = _normalize_url(url)
    if not target:
        return "unknown"
    inline = os.environ.get("LISTING_LIVE_BROWSER_INLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not inline:
        status = _probe_listing_browser_subprocess(target, listing_id=listing_id)
        if status != "unknown":
            return status
    return _probe_listing_browser_inline(target, listing_id=listing_id)


def _probe_listing_browser_subprocess(
    url: str,
    *,
    listing_id: int | None = None,
) -> LiveStatus:
    import subprocess
    import sys

    helper = Path(__file__).resolve().parents[1] / "tools" / "probe_listing_live.py"
    if not helper.is_file():
        return "unknown"
    python = os.environ.get("LISTING_LIVE_PYTHON", "").strip() or sys.executable
    env = os.environ.copy()
    env["LISTING_LIVE_BROWSER_INLINE"] = "1"
    env["PYTHONPATH"] = str(helper.parents[1]) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    cmd = [python, str(helper), url]
    if listing_id is not None:
        cmd.append(str(listing_id))
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=max(15.0, _PROBE_TIMEOUT_SEC),
            env=env,
            cwd=str(helper.parents[1]),
        )
    except Exception as exc:
        logger.info("listing live subprocess failed for %s: %s", url, exc)
        return "unknown"
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    value = (lines[-1] if lines else "unknown").lower()
    if value in {"available", "unavailable", "unknown"}:
        return value  # type: ignore[return-value]
    logger.info(
        "listing live subprocess unexpected output for %s rc=%s out=%r err=%r",
        url,
        completed.returncode,
        (completed.stdout or "")[-300:],
        (completed.stderr or "")[-300:],
    )
    return "unknown"


def _probe_listing_browser_inline(
    url: str,
    *,
    listing_id: int | None = None,
) -> LiveStatus:
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
            try:
                context = create_browser_context(
                    playwright,
                    headless=True,
                    profile_dir=profile,
                    storage_state=None,
                )
            except Exception as exc:
                if profile is None:
                    raise
                logger.info("listing live profile unavailable (%s); retry without profile", exc)
                context = create_browser_context(
                    playwright,
                    headless=True,
                    profile_dir=None,
                    storage_state=None,
                )
            page = context.new_page()
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=_BROWSER_TIMEOUT_MS)
                page.wait_for_timeout(1200)
                title = page.title() or ""
                html = page.content()
                final_url = page.url or target
                return classify_listing_html(
                    status_code=200,
                    url=final_url,
                    title=title,
                    html=html,
                    listing_id=listing_id,
                )
            finally:
                context.close()
    except Exception as exc:
        logger.info("listing live browser probe failed for %s: %s", target, exc)
        return "unknown"


def _probe_uncached(url: str, *, listing_id: int | None = None) -> LiveStatus:
    status = probe_listing_http(url, listing_id=listing_id)
    if status == "unknown" and _browser_enabled():
        status = probe_listing_browser(url, listing_id=listing_id)
    return status


def probe_listing_url(url: str, *, listing_id: int | None = None) -> LiveStatus:
    """Return live status for a listing URL (cached, off gevent worker thread)."""
    target = _normalize_url(url)
    if not target:
        return "unknown"
    cache_key = f"{listing_id or ''}::{target}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    with _inflight_lock:
        event = _inflight.get(cache_key)
        leader = event is None
        if leader:
            event = threading.Event()
            _inflight[cache_key] = event
    if not leader:
        event.wait(timeout=_PROBE_TIMEOUT_SEC + 5.0)
        return _cache_get(cache_key) or "unknown"

    try:
        future = _executor.submit(_probe_uncached, target, listing_id=listing_id)
        try:
            status = future.result(timeout=_PROBE_TIMEOUT_SEC)
        except FuturesTimeout:
            logger.info("listing live probe timed out for %s", target)
            status = "unknown"
        return _cache_set(cache_key, status)
    finally:
        with _inflight_lock:
            _inflight.pop(cache_key, None)
        event.set()
