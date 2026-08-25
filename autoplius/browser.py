from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from autoplius.captcha import CaptchaError, TurnstileSolution, load_api_key, solve_turnstile_challenge

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

HOOK_SCRIPT = (Path(__file__).resolve().parent / "turnstile_hook.js").read_text(encoding="utf-8")

CHALLENGE_MARKERS = (
    "just a moment",
    "luktelėkite",
    "luktelkite",
    "tikriname jūsų naršyklę",
    "please confirm that you are not a robot",
    "prašome patvirtinti kad esate ne robotas",
    "cf-turnstile",
    "challenge-platform",
)

STEALTH_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


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


def has_target_content(page: Page, html: str) -> bool:
    if page.locator("a.announcement-item").count() > 0:
        return True
    if page.locator(".second-parameters .parameter-row").count() > 0:
        return True
    if "announcement-item" in html or "second-parameters" in html:
        return True
    return False


def dismiss_cookie_banner(page: Page) -> None:
    for selector in (
        "button:has-text('Sutinku')",
        "button:has-text('Accept all')",
        "button:has-text('Leisti visus')",
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
        print("Turnstile params not captured yet, reloading challenge page...", flush=True)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        params = wait_for_turnstile_params(page, interceptor, timeout_sec=25.0)
    if not params:
        raise CaptchaError(
            "Could not intercept turnstile.render params. "
            "Cloudflare may have changed the challenge widget."
        )

    print(
        f"Solving Cloudflare Turnstile via 2Captcha for {params.get('websiteURL') or page.url}...",
        flush=True,
    )
    solution = solve_turnstile_challenge(api_key, params)
    mode = apply_turnstile_token(page, solution.token)
    print(f"2Captcha token applied via {mode}", flush=True)
    page.wait_for_timeout(3000)
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
    max_captcha_attempts = 2

    while time.monotonic() < deadline:
        title = page.title() or ""
        html = page.content()

        if is_challenge_page(html, title):
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
                    print(f"2Captcha solve failed: {exc}", flush=True)
                continue

            page.wait_for_timeout(2000)
            continue

        if page.locator("h1").filter(has_text=re.compile(r"404|not found", re.I)).count() > 0:
            raise RuntimeError(f"Page not found: {page.url}")

        if has_target_content(page, html):
            return

        page.wait_for_timeout(1000)

    tips = (
        "Tip: set CAPTCHA_2CAPTCHA_API_KEY in .env, "
        "or reuse --profile-dir with saved cookies."
    )
    raise TimeoutError(f"Timed out waiting for Autoplius content: {page.url}\n{tips}")


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

    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            channel="chrome",
            locale="lt-LT",
            viewport={"width": 1366, "height": 900},
            args=launch_args,
            user_agent=user_agent,
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
        "locale": "lt-LT",
        "viewport": {"width": 1366, "height": 900},
        "user_agent": user_agent,
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
