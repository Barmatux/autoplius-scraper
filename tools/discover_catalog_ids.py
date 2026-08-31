#!/usr/bin/env python3
"""Discover Autoplius make/model IDs via Playwright (uses browser profile)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.browser import create_browser_context, goto_and_wait
from autoplius.urls import configure_base_url, get_base_url

DEFAULT_MAKES = (
    "Peugeot",
    "Nissan",
    "Renault",
    "Hyundai",
    "Kia",
    "Ford",
)
DEFAULT_MODELS = (
    "3008",
    "5008",
    "Qashqai",
    "Grand Scenic",
    "Scenic",
    "i40",
    "Optima",
    "S-Max",
    "S Max",
    "Galaxy",
)


def _parse_make_links(html: str) -> dict[str, int]:
    makes: dict[str, int] = {}
    for match in re.finditer(
        r"make_id_list=(\d+)(?:&[^\"'>\s]*)?[\"'][^>]*>([^<]+)",
        html,
        flags=re.I,
    ):
        name = match.group(2).strip()
        if name and name not in makes:
            makes[name] = int(match.group(1))
    for match in re.finditer(
        r"data-make-id=[\"'](\d+)[\"'][^>]*>([^<]+)",
        html,
        flags=re.I,
    ):
        name = match.group(2).strip()
        if name and name not in makes:
            makes[name] = int(match.group(1))
    return makes


def _parse_model_links(html: str) -> dict[str, int]:
    models: dict[str, int] = {}
    for match in re.finditer(
        r"model_id_list=(\d+)(?:&[^\"'>\s]*)?[\"'][^>]*>([^<]+)",
        html,
        flags=re.I,
    ):
        name = match.group(2).strip()
        if name and name not in models:
            models[name] = int(match.group(1))
    for match in re.finditer(
        r"data-model-id=[\"'](\d+)[\"'][^>]*>([^<]+)",
        html,
        flags=re.I,
    ):
        name = match.group(2).strip()
        if name and name not in models:
            models[name] = int(match.group(1))
    return models


def discover(
    *,
    profile_dir: Path,
    headless: bool,
    makes: tuple[str, ...],
    model_hints: tuple[str, ...],
) -> dict[str, object]:
    configure_base_url("https://ru.autoplius.lt")
    base = get_base_url()
    result: dict[str, object] = {"makes": {}, "models_by_make": {}}

    with sync_playwright() as pw:
        ctx, page = create_browser_context(
            pw,
            headless=headless,
            profile_dir=profile_dir,
            storage_state=None,
            interceptor=None,
        )
        try:
            goto_and_wait(
                page,
                f"{base}/skelbimai/paieska?category_id=2&filter=makes",
                timeout_sec=120,
                auto_captcha=True,
                captcha_api_key=None,
            )
            all_makes = _parse_make_links(page.content())
            selected_makes = {
                name: all_makes[name]
                for name in makes
                if name in all_makes
            }
            result["makes"] = selected_makes
            result["all_make_count"] = len(all_makes)

            models_by_make: dict[str, dict[str, int]] = {}
            for make_name, make_id in selected_makes.items():
                goto_and_wait(
                    page,
                    (
                        f"{base}/skelbimai/paieska?category_id=2"
                        f"&filter=models&make_id_list={make_id}"
                    ),
                    timeout_sec=120,
                    auto_captcha=True,
                    captcha_api_key=None,
                )
                models = _parse_model_links(page.content())
                picked: dict[str, int] = {}
                for hint in model_hints:
                    for model_name, model_id in models.items():
                        if hint.casefold() in model_name.casefold():
                            picked[model_name] = model_id
                models_by_make[make_name] = picked or models
            result["models_by_make"] = models_by_make
        finally:
            ctx.close()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path("/var/lib/autoplius-scraper/browser-profile"),
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "catalog_ids.json",
    )
    args = parser.parse_args()

    data = discover(
        profile_dir=args.profile_dir,
        headless=not args.headed,
        makes=DEFAULT_MAKES,
        model_hints=DEFAULT_MODELS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
