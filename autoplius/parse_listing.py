from __future__ import annotations

import re

from bs4 import BeautifulSoup

from autoplius.models import ListingDetail
from autoplius.urls import extract_listing_id

PRICE_RE = re.compile(r"([\d\s]+)\s*(?:€|<span[^>]*>€</span>)")
PHONE_RE = re.compile(r"\+370[\d\s]{7,}")


def _parse_price(soup: BeautifulSoup) -> int | None:
    price_el = soup.select_one(".announcement-price .price, .parameter-row-price .price")
    if price_el:
        parsed = PRICE_RE.search(price_el.get_text(" ", strip=True).replace("\xa0", " "))
        if parsed:
            digits = re.sub(r"\D", "", parsed.group(1))
            if digits:
                return int(digits)

    for script in soup.find_all("script"):
        text = script.string or ""
        match = re.search(r'var\s+price\s*=\s*"(\d+)"', text)
        if match:
            return int(match.group(1))
    return None


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
        text = re.sub(r"\s*(Rodyti|Show)\s*", "", text, flags=re.I).strip()
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

    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc.get("content", "").strip() if meta_desc else None

    return ListingDetail(
        autoplius_id=listing_id,
        url=url.split("#", 1)[0],
        title=title,
        price_eur=_parse_price(soup),
        description=description or None,
        phone=_parse_phone(soup),
        vin_masked=_parse_vin_masked(soup),
        parameters=_parse_parameters(soup),
        photo_urls=_parse_photos(soup),
    )
