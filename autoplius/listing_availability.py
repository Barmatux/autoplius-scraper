"""Probe whether a listing URL is still live on Autoplius."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from autoplius.browser import is_challenge_page, is_not_found_page
from autoplius.urls import get_base_url

logger = logging.getLogger(__name__)

LiveStatus = Literal["available", "unavailable", "unknown"]

REASON_LABELS = {
    "available": "Объявление доступно на Autoplius",
    "unavailable": "Объявление недоступно на Autoplius",
    "cloudflare": "Cloudflare блокирует проверку с сервера",
    "timeout": "Таймаут проверки",
    "http_error": "Ошибка сети при обращении к Autoplius",
    "browser_error": "Не удалось открыть страницу через браузер",
    "no_content": "Страница открылась, но карточка объявления не распознана",
    "server_error": "Autoplius вернул ошибку сервера",
}

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

_cache: dict[str, tuple[float, "LiveProbeResult"]] = {}
_cache_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="listing-live")
_inflight: dict[str, threading.Event] = {}
_inflight_lock = threading.Lock()


@dataclass(frozen=True)
class LiveProbeResult:
    status: LiveStatus
    reason: str | None = None

    @property
    def reason_label(self) -> str:
        if self.reason and self.reason in REASON_LABELS:
            return REASON_LABELS[self.reason]
        if self.status == "available":
            return REASON_LABELS["available"]
        if self.status == "unavailable":
            return REASON_LABELS["unavailable"]
        return "Не удалось проверить актуальность"


def _normalize_url(url: str) -> str:
    return (url or "").strip()


def _cache_get(key: str) -> LiveProbeResult | None:
    with _cache_lock:
        hit = _cache.get(key)
        if not hit:
            return None
        expires_at, result = hit
        if expires_at < time.monotonic():
            _cache.pop(key, None)
            return None
        return result


def _cache_set(key: str, result: LiveProbeResult) -> LiveProbeResult:
    ttl = _UNKNOWN_CACHE_TTL_SEC if result.status == "unknown" else _CACHE_TTL_SEC
    with _cache_lock:
        _cache[key] = (time.monotonic() + max(15.0, ttl), result)
    return result


def classify_listing_html(
    *,
    status_code: int,
    url: str,
    title: str,
    html: str,
    listing_id: int | None = None,
) -> LiveProbeResult:
    """Classify an Autoplius response without performing network I/O."""
    final_url = (url or "").lower()
    if status_code == 404 or status_code == 410:
        return LiveProbeResult("unavailable", "unavailable")
    if status_code >= 500:
        return LiveProbeResult("unknown", "server_error")
    if is_not_found_page(title, html) or _is_inactive_listing(title, html):
        return LiveProbeResult("unavailable", "unavailable")
    if "/404" in final_url or final_url.rstrip("/").endswith("/not-found"):
        return LiveProbeResult("unavailable", "unavailable")
    if is_challenge_page(html, title) or status_code in {401, 403, 429}:
        return LiveProbeResult("unknown", "cloudflare")
    if status_code == 200 and _looks_like_active_listing(html, listing_id=listing_id):
        return LiveProbeResult("available", "available")
    if status_code == 200:
        return LiveProbeResult("unknown", "no_content")
    return LiveProbeResult("unknown", "http_error")


def _is_inactive_listing(title: str, html: str) -> bool:
    blob = f"{title}\n{html}"
    return bool(_INACTIVE_LISTING_RE.search(blob))


def _looks_like_active_listing(html: str, *, listing_id: int | None = None) -> bool:
    """Require detail-page markers; ignore search/404 pages with related ads."""
    blob = html.lower()
    if "second-parameters" not in blob or "parameter-row" not in blob:
        return False
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
    return bool(re.search(rf"(?<!\d){re.escape(sid)}(?!\d)", html))


def probe_listing_http(
    url: str,
    *,
    timeout: float | None = None,
    listing_id: int | None = None,
) -> LiveProbeResult:
    target = _normalize_url(url)
    if not target:
        return LiveProbeResult("unknown", "http_error")
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return LiveProbeResult("unknown", "http_error")

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
        return LiveProbeResult("unknown", "http_error")

    if "text/html" not in content_type and raw[:1] not in (b"<", b"!"):
        if status_code in {401, 403, 429}:
            return LiveProbeResult("unknown", "cloudflare")
        if status_code == 200:
            return LiveProbeResult("unknown", "no_content")

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


def probe_listing_browser(url: str, *, listing_id: int | None = None) -> LiveProbeResult:
    target = _normalize_url(url)
    if not target:
        return LiveProbeResult("unknown", "browser_error")
    inline = os.environ.get("LISTING_LIVE_BROWSER_INLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not inline:
        result = _probe_listing_browser_subprocess(target, listing_id=listing_id)
        if result.status != "unknown" or result.reason not in {None, "browser_error"}:
            return result
        if result.reason == "cloudflare":
            return result
    return _probe_listing_browser_inline(target, listing_id=listing_id)


def _probe_listing_browser_subprocess(
    url: str,
    *,
    listing_id: int | None = None,
) -> LiveProbeResult:
    import subprocess
    import sys

    helper = Path(__file__).resolve().parents[1] / "tools" / "probe_listing_live.py"
    if not helper.is_file():
        return LiveProbeResult("unknown", "browser_error")
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
        return LiveProbeResult("unknown", "browser_error")
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    raw = lines[-1] if lines else "unknown"
    if ":" in raw:
        status, reason = raw.split(":", 1)
    else:
        status, reason = raw, ""
    status = status.lower().strip()
    reason = reason.strip() or None
    if status in {"available", "unavailable", "unknown"}:
        return LiveProbeResult(status, reason)  # type: ignore[arg-type]
    logger.info(
        "listing live subprocess unexpected output for %s rc=%s out=%r err=%r",
        url,
        completed.returncode,
        (completed.stdout or "")[-300:],
        (completed.stderr or "")[-300:],
    )
    return LiveProbeResult("unknown", "browser_error")


def _probe_listing_browser_inline(
    url: str,
    *,
    listing_id: int | None = None,
) -> LiveProbeResult:
    target = _normalize_url(url)
    if not target:
        return LiveProbeResult("unknown", "browser_error")
    try:
        from playwright.sync_api import sync_playwright

        from autoplius.browser import create_browser_context
    except Exception as exc:
        logger.info("listing live browser unavailable: %s", exc)
        return LiveProbeResult("unknown", "browser_error")

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
        return LiveProbeResult("unknown", "browser_error")


def _probe_uncached(url: str, *, listing_id: int | None = None) -> LiveProbeResult:
    result = probe_listing_http(url, listing_id=listing_id)
    if result.status == "unknown" and result.reason == "cloudflare" and _browser_enabled():
        browser_result = probe_listing_browser(url, listing_id=listing_id)
        if browser_result.status != "unknown" or browser_result.reason not in {
            None,
            "browser_error",
        }:
            return browser_result
        # Prefer the more specific Cloudflare reason when browser also fails open.
        return result if result.reason else browser_result
    if result.status == "unknown" and _browser_enabled():
        return probe_listing_browser(url, listing_id=listing_id)
    return result


def probe_listing_url(url: str, *, listing_id: int | None = None) -> LiveStatus:
    return probe_listing_result(url, listing_id=listing_id).status


def probe_listing_result(url: str, *, listing_id: int | None = None) -> LiveProbeResult:
    """Return live status + reason for a listing URL (cached, off gevent worker)."""
    target = _normalize_url(url)
    if not target:
        return LiveProbeResult("unknown", "http_error")
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
        return _cache_get(cache_key) or LiveProbeResult("unknown", "timeout")

    try:
        future = _executor.submit(_probe_uncached, target, listing_id=listing_id)
        try:
            result = future.result(timeout=_PROBE_TIMEOUT_SEC)
        except FuturesTimeout:
            logger.info("listing live probe timed out for %s", target)
            result = LiveProbeResult("unknown", "timeout")
        return _cache_set(cache_key, result)
    finally:
        with _inflight_lock:
            _inflight.pop(cache_key, None)
        event.set()
