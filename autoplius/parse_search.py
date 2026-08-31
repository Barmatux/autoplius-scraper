from __future__ import annotations

import re

from bs4 import BeautifulSoup

from autoplius.models import SearchListingPreview
from autoplius.urls import extract_listing_id, normalize_listing_url

PRICE_RE = re.compile(r"([\d\s]+)\s*€")
MILEAGE_RE = re.compile(r"([\d\s]+)\s*km", re.I)


def _parse_price(text: str) -> int | None:
    match = PRICE_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def _parse_mileage(text: str) -> int | None:
    match = MILEAGE_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def parse_search_html(html: str) -> list[SearchListingPreview]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchListingPreview] = []
    seen: set[int] = set()

    cards = soup.select("a.announcement-item")
    if not cards:
        cards = [
            a
            for a in soup.select("a[href$='.html']")
            if extract_listing_id(a.get("href") or "")
            and "naudoti-automobiliai" not in (a.get("href") or "")
            and "b-u-avtomobili" not in (a.get("href") or "")
        ]

    for item in cards:
        href = item.get("href") or ""
        if not href or "naudoti-automobiliai" in href or href.rstrip("/").endswith("b-u-avtomobili"):
            continue
        listing_id = extract_listing_id(href)
        if listing_id is None or listing_id in seen:
            continue
        seen.add(listing_id)

        title_el = item.select_one(".announcement-title")
        title = title_el.get_text(strip=True) if title_el else ""

        param_spans = item.select(".announcement-parameters span")
        year = param_spans[0].get_text(strip=True) if len(param_spans) > 0 else None
        body_type = param_spans[1].get_text(strip=True) if len(param_spans) > 1 else None

        price_el = item.select_one(".announcement-pricing-info strong")
        price_eur = _parse_price(price_el.get_text(" ", strip=True)) if price_el else None

        secondary = item.select(".announcement-parameters-block span, .announcement-secondary-parameters span")
        secondary_texts = [s.get_text(" ", strip=True) for s in secondary]

        fuel = transmission = engine = city = None
        mileage_km = None
        for chunk in secondary_texts:
            low = chunk.lower()
            if "km" in low:
                mileage_km = _parse_mileage(chunk)
            elif any(
                x in low
                for x in (
                    "automatin",
                    "mechanin",
                    "автомат",
                    "механ",
                    "robot",
                    "вариатор",
                )
            ):
                transmission = chunk
            elif any(
                x in low
                for x in (
                    "dyzel",
                    "benzin",
                    "elektr",
                    "dujos",
                    "hibrid",
                    "vandenil",
                    "дизел",
                    "бенз",
                    "элект",
                    "газ",
                    "гибрид",
                )
            ):
                fuel = chunk
            elif " l" in low or " kwh" in low:
                engine = chunk
            elif chunk and not re.search(r"\d", chunk) and len(chunk) < 40:
                city = chunk

        photo_el = item.select_one(".announcement-photo img")
        photo_url = None
        if photo_el:
            photo_url = photo_el.get("src") or photo_el.get("data-src")
            if not photo_url:
                srcset = photo_el.get("srcset") or ""
                photo_url = srcset.split()[0] if srcset else None

        badges_text = item.select_one(".announcement-badges")
        has_vin = bool(badges_text and "vin" in badges_text.get_text(" ", strip=True).lower())

        results.append(
            SearchListingPreview(
                autoplius_id=listing_id,
                url=normalize_listing_url(href.split("#", 1)[0]),
                title=title,
                year=year,
                body_type=body_type,
                price_eur=price_eur,
                fuel=fuel,
                transmission=transmission,
                engine=engine,
                mileage_km=mileage_km,
                city=city,
                photo_url=photo_url,
                has_vin_badge=has_vin,
            )
        )

    return results
