from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from autoplius.captcha import CaptchaError, TurnstileSolution, load_api_key, solve_turnstile_challenge
from autoplius.urls import get_base_url

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger(__name__)

HOOK_SCRIPT = (Path(__file__).resolve().parent / "turnstile_hook.js").read_text(encoding="utf-8")

CHALLENGE_MARKERS = (
    "just a moment",
    "luktelėkite",
    "luktelkite",
    "tikriname jūsų naršyklę",
    "please confirm that you are not a robot",
    "prašome patvirtinti kad esate ne robotas",
    "we are verifying your browser",
    "enable javascript and cookies",
    "cf-turnstile",
    "challenge-platform",
    "проверяем ваш браузер",
    "подтвердите, что вы не робот",
    "подтвердите что вы не робот",
)

STEALTH_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)

_NOT_FOUND_TITLE_RE = re.compile(r"\b404\b|not found|не найдена", re.I)
_NOT_FOUND_H1_RE = re.compile(r"\b404\b|not found|не найдена", re.I)


def browser_locale(base_url: str | None = None) -> str:
    host = urlparse(base_url or get_base_url()).netloc.lower()
    if host.startswith("ru."):
        return "ru-RU"
    if host.startswith("en."):
        return "en-US"
    return "lt-LT"


class TurnstileInterceptor:
    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None
        self._context: BrowserContext | None = None

    def reset(self) -> None:
        self.params = None

    def _on_params(self, raw: str) -> None:
        self.params = json.loads(raw)

    def install(self, context: BrowserContext) -> None:
        if self._context is context:
            return
        self._context = context
        context.expose_function("__reportTurnstileParams", self._on_params)
        context.add_init_script(STEALTH_INIT_SCRIPT)
        context.add_init_script(HOOK_SCRIPT)

    def read_params_from_page(self, page: Page) -> dict[str, Any] | None:
        if self.params:
            return self.params
        try:
            raw = page.evaluate(
                """() => {
                    if (!window.__cfTurnstileParams) return null;
                    return JSON.stringify(window.__cfTurnstileParams);
                }"""
            )
        except Exception:
            return None
        if not raw:
            return None
        self.params = json.loads(raw)
        return self.params


def is_challenge_page(html: str, title: str = "") -> bool:
    blob = f"{title}\n{html}".lower()
    return any(marker in blob for marker in CHALLENGE_MARKERS)


def is_not_found_page(title: str, html: str) -> bool:
    """Detect Autoplius 404 pages without matching listing IDs like A31404018."""
    if _NOT_FOUND_TITLE_RE.search(title):
        return True
    return "страница не найдена" in html.lower()


def has_target_content(page: Page, html: str) -> bool:
    if page.locator("a.announcement-item").count() > 0:
        return True
    if page.locator(".second-parameters .parameter-row").count() > 0:
        return True
    if page.locator("a[href*='/skelbimai/'][href$='.html']").count() > 3:
        return True
    if page.locator("a[href*='/objavlenija/'][href$='.html']").count() > 3:
        return True
    if "announcement-item" in html or "second-parameters" in html:
        return True
    if html.count(".html") >= 8 and ("/skelbimai/" in html or "/objavlenija/" in html):
        return True
    return False


def dismiss_cookie_banner(page: Page) -> None:
    for selector in (
        "button:has-text('Sutinku')",
        "button:has-text('Accept all')",
        "button:has-text('Leisti visus')",
        "button:has-text('Согласен')",
        "button:has-text('Принять все')",
        "button:has-text('Принять')",
        "#onetrust-accept-btn-handler",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=2000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def apply_turnstile_token(page: Page, token: str) -> str:
    return page.evaluate(
        """(token) => {
            if (typeof window.__cfTurnstileCallback === 'function') {
                window.__cfTurnstileCallback(token);
                return 'callback';
            }
            const input = document.querySelector('[name="cf-turnstile-response"]');
            if (input) {
                input.value = token;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return 'input';
            }
            return 'missing';
        }""",
        token,
    )


def wait_for_turnstile_params(
    page: Page,
    interceptor: TurnstileInterceptor,
    *,
    timeout_sec: float = 25.0,
) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        params = interceptor.read_params_from_page(page)
        if params:
            return params
        page.wait_for_timeout(250)
    return None


def solve_cloudflare_turnstile(
    page: Page,
    interceptor: TurnstileInterceptor,
    *,
    api_key: str,
) -> TurnstileSolution:
    interceptor.reset()
    params = wait_for_turnstile_params(page, interceptor, timeout_sec=20.0)
    if not params:
        logger.warning("Turnstile params not captured, reloading challenge page")
        page.reload(wait_until="domcontentloaded", timeout=60000)
        params = wait_for_turnstile_params(page, interceptor, timeout_sec=25.0)
    if not params:
        raise CaptchaError(
            "Could not intercept turnstile.render params. "
            "Cloudflare may have changed the challenge widget."
        )

    logger.info("Solving Cloudflare Turnstile via 2Captcha for %s", params.get("websiteURL") or page.url)
    solution = solve_turnstile_challenge(api_key, params)
    mode = apply_turnstile_token(page, solution.token)
    logger.info("2Captcha token applied via %s", mode)
    page.wait_for_timeout(2500)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    html = page.content()
    title = page.title() or ""
    if is_challenge_page(html, title) and not has_target_content(page, html):
        logger.info("Challenge still visible after token, reloading")
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
    return solution


def wait_for_content(
    page: Page,
    *,
    timeout_sec: float = 90.0,
    manual: bool = False,
    auto_captcha: bool = False,
    captcha_api_key: str | None = None,
    interceptor: TurnstileInterceptor | None = None,
) -> None:
    """Wait until Cloudflare challenge passes and listing/search markup appears."""
    deadline = time.monotonic() + timeout_sec
    captcha_attempts = 0
    max_captcha_attempts = 4

    while time.monotonic() < deadline:
        title = page.title() or ""
        html = page.content()

        if is_challenge_page(html, title):
            logger.info("Cloudflare challenge on %s (%s)", page.url, title[:80])
            if manual:
                print(
                    "\nCloudflare challenge detected. "
                    "Complete it in the browser window, then press Enter here...",
                    flush=True,
                )
                input()
                continue

            if (
                auto_captcha
                and captcha_api_key
                and interceptor is not None
                and captcha_attempts < max_captcha_attempts
            ):
                captcha_attempts += 1
                try:
                    solve_cloudflare_turnstile(
                        page,
                        interceptor,
                        api_key=captcha_api_key,
                    )
                except CaptchaError as exc:
                    logger.warning("2Captcha solve failed: %s", exc)
                dismiss_cookie_banner(page)
                continue

            page.wait_for_timeout(2000)
            continue

        if has_target_content(page, html):
            dismiss_cookie_banner(page)
            return

        if page.locator("h1").filter(has_text=_NOT_FOUND_H1_RE).count() > 0:
            raise RuntimeError(f"Page not found: {page.url}")
        if is_not_found_page(title, html):
            raise RuntimeError(f"Page not found: {page.url}")

        page.wait_for_timeout(1000)

    title = page.title() or ""
    html = page.content()
    snippet = re.sub(r"\s+", " ", _visible_text(html))[:400]
    logger.error(
        "Timed out on %s title=%r challenge=%s listings=%s snippet=%s",
        page.url,
        title,
        is_challenge_page(html, title),
        has_target_content(page, html),
        snippet,
    )
    tips = (
        "Tip: set CAPTCHA_2CAPTCHA_API_KEY in .env, "
        "or reuse --profile-dir with saved cookies."
    )
    raise TimeoutError(f"Timed out waiting for Autoplius content: {page.url}\n{tips}")


def _visible_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        return html[:400]


def create_browser_context(
    playwright,
    *,
    headless: bool,
    profile_dir: Path | None,
    storage_state: Path | None,
    interceptor: TurnstileInterceptor | None = None,
):
    launch_args = ["--disable-blink-features=AutomationControlled"]
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    locale = browser_locale()
    accept_language = "ru-RU,ru;q=0.9,en;q=0.8" if locale.startswith("ru") else "lt-LT,lt;q=0.9,en;q=0.8"

    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            channel="chrome",
            locale=locale,
            viewport={"width": 1366, "height": 900},
            args=launch_args,
            user_agent=user_agent,
            extra_http_headers={"Accept-Language": accept_language},
        )
        if interceptor is not None:
            interceptor.install(context)
        else:
            context.add_init_script(STEALTH_INIT_SCRIPT)
        return context, context.pages[0] if context.pages else context.new_page()

    browser = playwright.chromium.launch(
        headless=headless,
        channel="chrome",
        args=launch_args,
    )
    context_kwargs = {
        "locale": locale,
        "viewport": {"width": 1366, "height": 900},
        "user_agent": user_agent,
        "extra_http_headers": {"Accept-Language": accept_language},
    }
    if storage_state and storage_state.is_file():
        context_kwargs["storage_state"] = str(storage_state)
    context = browser.new_context(**context_kwargs)
    if interceptor is not None:
        interceptor.install(context)
    else:
        context.add_init_script(STEALTH_INIT_SCRIPT)
    return browser, context.new_page()


def goto_and_wait(
    page: Page,
    url: str,
    *,
    timeout_sec: float = 90.0,
    manual: bool = False,
    auto_captcha: bool = False,
    captcha_api_key: str | None = None,
    interceptor: TurnstileInterceptor | None = None,
) -> None:
    if interceptor is not None:
        interceptor.reset()
    page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_sec * 1000))
    dismiss_cookie_banner(page)
    wait_for_content(
        page,
        timeout_sec=timeout_sec,
        manual=manual,
        auto_captcha=auto_captcha,
        captcha_api_key=captcha_api_key,
        interceptor=interceptor,
    )


def resolve_captcha_api_key(enabled: bool) -> str | None:
    if not enabled:
        return None
    return load_api_key()
