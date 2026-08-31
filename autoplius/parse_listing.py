from __future__ import annotations

import re

from bs4 import BeautifulSoup

from autoplius.models import ListingDetail
from autoplius.parse_price import parse_listing_prices, parse_price_amount
from autoplius.urls import extract_listing_id, normalize_listing_url
from typing import Any

PRICE_RE = re.compile(r"([\d\s]+)\s*(?:€|<span[^>]*>€</span>)")
PHONE_RE = re.compile(r"\+370[\d\s]{7,}")


def _parse_prices(soup: BeautifulSoup) -> dict[str, Any]:
    price_el = soup.select_one(".announcement-price .price, .parameter-row-price .price")
    main_text = price_el.get_text(" ", strip=True) if price_el else None
    if not parse_price_amount(main_text):
        for script in soup.find_all("script"):
            text = script.string or ""
            match = re.search(r'var\s+price\s*=\s*"(\d+)"', text)
            if match:
                main_text = f"{match.group(1)} €"
                break

    subtitle_el = soup.select_one(
        ".price-container .list-price-subtitle, "
        ".announcement-price .list-price-subtitle, "
        ".parameter-row-price .list-price-subtitle"
    )
    return parse_listing_prices(
        main_text=main_text,
        subtitle_text=subtitle_el.get_text(" ", strip=True) if subtitle_el else None,
    )


def _parse_parameters(soup: BeautifulSoup) -> dict[str, str]:
    params: dict[str, str] = {}

    for row in soup.select(".second-parameters .parameter-row"):
        label_el = row.select_one(".parameter-label")
        value_el = row.select_one(".parameter-value")
        if not label_el or not value_el:
            continue
        label = label_el.get_text(" ", strip=True)
        value = value_el.get_text(" ", strip=True)
        if label and value:
            params[label] = value

    for block in soup.select(".featured-paramter-container"):
        label_el = block.select_one(".featured-title")
        value_el = block.select_one(".featured-parameter")
        if not label_el or not value_el:
            continue
        label = label_el.get_text(" ", strip=True)
        value = value_el.get_text(" ", strip=True)
        if label and value and label not in params:
            params[label] = value

    return params


def _parse_vin_masked(soup: BeautifulSoup) -> str | None:
    for row in soup.select(".second-parameters .parameter-row"):
        label = row.select_one(".parameter-label")
        if not label:
            continue
        if "vin" not in label.get_text(" ", strip=True).lower():
            continue
        value_el = row.select_one(".parameter-value")
        if not value_el:
            continue
        text = value_el.get_text(" ", strip=True)
        text = re.sub(r"\s*(Rodyti|Show|Показать)\s*", "", text, flags=re.I).strip()
        return text or None
    return None


def _parse_photos(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for img in soup.select(
        ".announcement-gallery img, .gallery img, .announcement-photos img, picture source[srcset]"
    ):
        src = img.get("src") or img.get("data-src") or img.get("srcset") or ""
        src = src.split()[0] if src and " " in src else src
        if "autoplius-img" not in src or src in seen:
            continue
        seen.add(src)
        urls.append(src)

    if not urls:
        for meta in soup.find_all("meta", property="og:image"):
            src = meta.get("content") or ""
            if "autoplius-img" in src and src not in seen:
                seen.add(src)
                urls.append(src)
    return urls


def _parse_phone(soup: BeautifulSoup) -> str | None:
    for node in soup.select(
        ".seller-contact, .phone-number, .announcement-contacts, .contacts-container"
    ):
        match = PHONE_RE.search(node.get_text(" ", strip=True))
        if match:
            return re.sub(r"\s+", " ", match.group(0).strip())
    body = soup.get_text(" ", strip=True)
    match = PHONE_RE.search(body)
    return re.sub(r"\s+", " ", match.group(0).strip()) if match else None


def _parse_description(soup: BeautifulSoup) -> str | None:
    selectors = (
        ".announcement-description",
        ".announcement-description .value",
        ".description-content",
        "#description",
        "[itemprop='description']",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = node.get_text(" ", strip=True)
        if text and len(text) > 10:
            return text

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        text = meta_desc.get("content", "").strip()
        if text:
            return text
    return None


def parse_listing_html(html: str, url: str) -> ListingDetail:
    soup = BeautifulSoup(html, "html.parser")
    listing_id = extract_listing_id(url)
    if listing_id is None:
        raise ValueError(f"Cannot extract listing id from URL: {url}")

    title_el = soup.select_one("h1, .announcement-title")
    if title_el:
        title = title_el.get_text(" ", strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    else:
        title = ""

    description = _parse_description(soup)
    prices = _parse_prices(soup)

    return ListingDetail(
        autoplius_id=listing_id,
        url=normalize_listing_url(url.split("#", 1)[0]),
        title=title,
        price_eur=prices["price_eur"],
        price_net_eur=prices["price_net_eur"],
        price_gross_eur=prices["price_gross_eur"],
        price_vat_note=prices["price_vat_note"],
        description=description or None,
        phone=_parse_phone(soup),
        vin_masked=_parse_vin_masked(soup),
        parameters=_parse_parameters(soup),
        photo_urls=_parse_photos(soup),
    )
