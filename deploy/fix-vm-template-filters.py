#!/usr/bin/env python3
"""Register Jinja filters required by VM index.html overlays."""
from __future__ import annotations

from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")

ENGINE_KPP_BLOCK = '''

@app.template_filter("engine_kpp_lines")
def engine_kpp_lines(item: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    volume = engine_volume_from_listing(item)
    if volume:
        lines.append(volume.replace(" л", ""))
    fuel = (item.get("fuel") or "").strip()
    if fuel:
        lines.append(fuel)
    transmission = (item.get("transmission") or "").strip()
    if transmission:
        lines.append(transmission)
    mileage_km = item.get("mileage_km")
    if mileage_km is not None:
        lines.append(f"{int(mileage_km):,}".replace(",", " ") + " km")
    return lines
'''

CATALOG_PRICE_BLOCK = '''

@app.template_filter("catalog_price_lines")
def catalog_price_lines_filter(item: dict[str, Any]):
    return catalog_price_lines(item)
'''

BODY_TYPE_BLOCK = '''

@app.template_filter("body_type_lines")
def body_type_lines(body_type: str | None) -> list[str]:
    text = (body_type or "").strip()
    if not text:
        return []
    if " / " in text:
        left, right = text.split(" / ", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            return [left, right]
    return [text]
'''

DETAIL_FILTERS_BLOCK = '''

@app.template_filter("detail_scrape_pending")
def detail_scrape_pending(item: dict[str, Any]) -> bool:
    return bool(item) and not bool(item.get("detail_scraped"))


@app.template_filter("detail_error_public")
def detail_error_public(item: dict[str, Any]) -> str | None:
    if not item:
        return None
    error = (item.get("detail_error") or "").strip()
    return error or None
'''


def main() -> int:
    text = APP.read_text(encoding="utf-8")
    changed = False

    if "catalog_price_lines" not in text.split("@app.template_filter", 1)[0]:
        text = text.replace(
            "from autoplius.price_display import price_lt_lines\n",
            "from autoplius.price_display import catalog_price_lines, price_lt_lines\n",
            1,
        )
        changed = True

    if '@app.template_filter("engine_kpp_lines")' not in text:
        anchor = '@app.template_filter("engine_volume")\ndef engine_volume(item: dict[str, Any]) -> str:\n    return engine_volume_from_listing(item) or "—"\n'
        if anchor not in text:
            raise SystemExit("engine_volume anchor not found")
        text = text.replace(anchor, anchor + ENGINE_KPP_BLOCK, 1)
        changed = True

    if '@app.template_filter("catalog_price_lines")' not in text:
        anchor = '@app.template_filter("photo_srcs")\ndef photo_srcs(urls: list[str] | None) -> list[str]:\n    return photo_display_urls(urls)\n\n\n'
        if anchor not in text:
            raise SystemExit("photo_srcs anchor not found")
        text = text.replace(anchor, anchor + CATALOG_PRICE_BLOCK.lstrip("\n") + "\n\n", 1)
        changed = True

    if '@app.template_filter("body_type_lines")' not in text:
        anchor = '@app.template_filter("listing_make_model")'
        pos = text.find(anchor)
        if pos == -1:
            raise SystemExit("listing_make_model anchor not found")
        end = text.find("\n\n", text.find("return ", pos))
        if end == -1:
            raise SystemExit("listing_make_model block end not found")
        text = text[: end + 2] + BODY_TYPE_BLOCK.lstrip("\n") + text[end + 2 :]
        changed = True

    if '@app.template_filter("detail_scrape_pending")' not in text:
        anchor = '@app.template_filter("listing_description")\ndef listing_description(item: dict[str, Any]) -> str | None:\n    primary, _ = display_description(item)\n    if not primary:\n        return None\n    text = primary.strip()\n    return text or None\n\n\n'
        if anchor not in text:
            raise SystemExit("listing_description anchor not found")
        text = text.replace(anchor, anchor.rstrip("\n") + DETAIL_FILTERS_BLOCK + "\n\n", 1)
        changed = True

    if changed:
        APP.write_text(text, encoding="utf-8")
        print("OK patched", APP)
    else:
        print("already patched", APP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
