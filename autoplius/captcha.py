from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "https://api.2captcha.com"


@dataclass
class TurnstileSolution:
    token: str
    user_agent: str | None = None
    cost: str | None = None


class CaptchaError(RuntimeError):
    pass


def load_api_key() -> str:
    for name in ("CAPTCHA_2CAPTCHA_API_KEY", "TWOCAPTCHA_API_KEY", "RUCAPTCHA_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value

    project_root = Path(__file__).resolve().parents[1]
    repo_root = project_root.parent
    for env_path in (
        project_root / ".env",
        repo_root / "backend" / ".env.vm",
        repo_root / "backend" / ".env",
        Path(".env"),
    ):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in {
                "CAPTCHA_2CAPTCHA_API_KEY",
                "TWOCAPTCHA_API_KEY",
                "RUCAPTCHA_API_KEY",
            }:
                cleaned = value.strip().strip('"').strip("'")
                if cleaned:
                    os.environ[key.strip()] = cleaned
                    return cleaned

    raise CaptchaError(
        "2Captcha API key not found. Set CAPTCHA_2CAPTCHA_API_KEY in .env"
    )


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 60.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise CaptchaError(f"HTTP {exc.code} from 2Captcha: {raw}") from exc
    except urllib.error.URLError as exc:
        raise CaptchaError(f"2Captcha request failed: {exc}") from exc


def get_balance(api_key: str, *, api_base: str = DEFAULT_API_BASE) -> float:
    payload = _post_json(f"{api_base}/getBalance", {"clientKey": api_key})
    if payload.get("errorId"):
        raise CaptchaError(f"2Captcha balance error: {payload}")
    return float(payload["balance"])


def solve_turnstile_challenge(
    api_key: str,
    params: dict[str, Any],
    *,
    api_base: str = DEFAULT_API_BASE,
    poll_interval_sec: float = 5.0,
    timeout_sec: float = 180.0,
) -> TurnstileSolution:
    website_key = params.get("websiteKey") or params.get("sitekey")
    website_url = params.get("websiteURL") or params.get("pageurl")
    if not website_key or not website_url:
        raise CaptchaError(f"Incomplete Turnstile params: {params}")

    task: dict[str, Any] = {
        "type": "TurnstileTaskProxyless",
        "websiteURL": website_url,
        "websiteKey": website_key,
    }
    for src, dst in (("action", "action"), ("data", "data"), ("pagedata", "pagedata")):
        value = params.get(src)
        if value:
            task[dst] = value

    create = _post_json(
        f"{api_base}/createTask",
        {"clientKey": api_key, "task": task},
    )
    if create.get("errorId"):
        raise CaptchaError(f"2Captcha createTask failed: {create}")

    task_id = create.get("taskId")
    if not task_id:
        raise CaptchaError(f"2Captcha createTask missing taskId: {create}")

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_interval_sec)
        result = _post_json(
            f"{api_base}/getTaskResult",
            {"clientKey": api_key, "taskId": task_id},
        )
        if result.get("errorId"):
            raise CaptchaError(f"2Captcha getTaskResult failed: {result}")

        status = result.get("status")
        if status == "processing":
            continue
        if status != "ready":
            raise CaptchaError(f"Unexpected 2Captcha status: {result}")

        solution = result.get("solution") or {}
        token = solution.get("token")
        if not token:
            raise CaptchaError(f"2Captcha ready but token missing: {result}")

        return TurnstileSolution(
            token=token,
            user_agent=solution.get("userAgent"),
            cost=str(result.get("cost")) if result.get("cost") is not None else None,
        )

    raise CaptchaError(f"2Captcha timeout after {timeout_sec}s for task {task_id}")
