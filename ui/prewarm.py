"""Warm anonymous home HTML into gunicorn page_cache (and optionally nginx)."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Default listing view + brand/nav link (different query → different cache keys).
DEFAULT_HOME_PATHS = (
    "/",
    "/?tab=all&sort=added_desc",
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if raw.isdigit():
        return max(0, int(raw))
    return default


def home_paths() -> tuple[str, ...]:
    raw = os.environ.get("UI_PREWARM_PATHS", "").strip()
    if not raw:
        return DEFAULT_HOME_PATHS
    paths = tuple(p.strip() for p in raw.split(",") if p.strip())
    return paths or DEFAULT_HOME_PATHS


def prewarm_home(
    *,
    base_url: str | None = None,
    paths: Iterable[str] | None = None,
    rounds: int | None = None,
    timeout_sec: float | None = None,
) -> list[dict[str, object]]:
    """GET home URLs so cold HTML lands in in-process page_cache.

    Multiple rounds help when gunicorn has more than one worker (round-robin).
    """
    base = (base_url or os.environ.get("UI_PREWARM_BASE") or "http://127.0.0.1:8080").rstrip(
        "/"
    )
    path_list = tuple(paths) if paths is not None else home_paths()
    n_rounds = rounds if rounds is not None else _env_int("UI_PREWARM_ROUNDS", 2)
    timeout = (
        float(timeout_sec)
        if timeout_sec is not None
        else float(_env_int("UI_PREWARM_TIMEOUT_SEC", 120))
    )
    results: list[dict[str, object]] = []
    ua = "eu2-prewarm/1.0"
    for round_i in range(max(1, n_rounds)):
        for path in path_list:
            if not path.startswith("/"):
                path = "/" + path
            url = f"{base}{path}"
            entry: dict[str, object] = {"url": url, "round": round_i + 1}
            try:
                req = urllib.request.Request(url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read()
                    entry["ok"] = True
                    entry["status"] = int(getattr(resp, "status", 200) or 200)
                    entry["bytes"] = len(body)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                entry["ok"] = False
                entry["error"] = str(exc)
                logger.warning("prewarm failed %s: %s", url, exc)
            results.append(entry)
            logger.info(
                "prewarm round=%s %s ok=%s status=%s",
                entry.get("round"),
                url,
                entry.get("ok"),
                entry.get("status"),
            )
    return results


def schedule_prewarm_home(**kwargs) -> None:
    """Fire-and-forget prewarm that survives scrape oneshot process exit.

    Prefers ``deploy/prewarm-home.sh`` in a new session; falls back to a
    daemon thread when the script is unavailable (local/dev).
    """
    if kwargs:
        # Custom kwargs → in-process thread (tests / explicit overrides).
        def _run() -> None:
            try:
                prewarm_home(**kwargs)
            except Exception:
                logger.exception("background prewarm failed")

        threading.Thread(target=_run, name="prewarm-home", daemon=True).start()
        return

    script = Path(__file__).resolve().parent.parent / "deploy" / "prewarm-home.sh"
    if script.is_file():
        log_dir = Path(os.environ.get("LOGS_DIR") or "/var/log/autoplius-scraper")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log_dir = Path(".")
        log_path = log_dir / "prewarm-home.log"
        try:
            log_f = open(log_path, "a", encoding="utf-8")
        except OSError:
            log_f = subprocess.DEVNULL
        try:
            subprocess.Popen(
                ["bash", str(script)],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=str(script.parent.parent),
            )
            logger.info("scheduled prewarm via %s (log=%s)", script, log_path)
            return
        except OSError as exc:
            logger.warning("could not spawn prewarm script: %s", exc)
            if log_f is not subprocess.DEVNULL:
                log_f.close()

    def _run_fallback() -> None:
        try:
            prewarm_home()
        except Exception:
            logger.exception("background prewarm failed")

    threading.Thread(target=_run_fallback, name="prewarm-home", daemon=True).start()
