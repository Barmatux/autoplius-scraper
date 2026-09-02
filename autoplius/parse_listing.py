from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from autoplius.models import ListingDetail
from autoplius.parse_price import parse_listing_prices, parse_price_amount
from autoplius.photo_urls import best_photo_url, is_autoplius_cdn_url, normalize_photo_list, photo_asset_key
from autoplius.urls import extract_listing_id, normalize_listing_url
from autoplius.listing_titles import is_invalid_listing_title, resolve_listing_title
from typing import Any

PRICE_RE = re.compile(r"([\d\s]+)\s*(?:€|<span[^>]*>€</span>)")
PHONE_RE = re.compile(r"\+370[\d\s]{7,}")
_MEDIA_GALLERY_ITEMS_RE = re.compile(
    r"var\s+mediaGalleryItems\s*=\s*(\[.*?\])\s*;",
    re.DOTALL,
)


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


def _photo_from_attrs(element) -> str | None:
    for attr in ("data-big", "data-src", "src", "content"):
        raw = element.get(attr)
        if not raw:
            continue
        clean = raw.strip().split()[0]
        if clean.startswith("data:"):
            continue
        if "autoplius-img" in clean or is_autoplius_cdn_url(clean):
            return best_photo_url(clean)
    if element.name == "source":
        for attr in ("data-big", "data-srcset", "srcset"):
            raw = element.get(attr)
            if not raw:
                continue
            clean = raw.strip().split()[0]
            if clean.startswith("data:"):
                continue
            if "autoplius-img" in clean or is_autoplius_cdn_url(clean):
                return best_photo_url(clean)
    return None


def _register_photo(
    bucket: dict[str, tuple[int, str]],
    url: str | None,
    *,
    sort_index: int,
) -> None:
    if not url:
        return
    key = photo_asset_key(url)
    existing = bucket.get(key)
    if existing is None or sort_index < existing[0]:
        bucket[key] = (sort_index, url)


def _parse_media_gallery_items(soup: BeautifulSoup) -> list[str]:
    """Full photo list from Autoplius lightbox JSON (often more than carousel slides)."""
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "mediaGalleryItems" not in text:
            continue
        match = _MEDIA_GALLERY_ITEMS_RE.search(text)
        if not match:
            continue
        try:
            items = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        urls: list[str] = []
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "photo":
                continue
            raw = item.get("url") or item.get("thumbnail")
            if raw:
                urls.append(best_photo_url(raw) or raw)
        if urls:
            return normalize_photo_list(urls)
    return []


def _parse_photos(soup: BeautifulSoup) -> list[str]:
    photos: dict[str, tuple[int, str]] = {}

    for idx, url in enumerate(_parse_media_gallery_items(soup)):
        _register_photo(photos, url, sort_index=idx)

    for thumb in soup.select(".media-gallery-thumbnails [data-index]"):
        sort_index = len(photos)
        if thumb.get("data-index", "").isdigit():
            sort_index = int(thumb["data-index"])
        url = None
        for element in thumb.select("[data-big], img, source"):
            url = _photo_from_attrs(element)
            if url:
                break
        _register_photo(photos, url, sort_index=sort_index)

    for slide in soup.select(".announcement-gallery-carousel__slide"):
        sort_index = len(photos)
        if slide.get("data-index", "").isdigit():
            sort_index = int(slide["data-index"])
        url = None
        for element in slide.select("[data-big], img, source"):
            url = _photo_from_attrs(element)
            if url:
                break
        _register_photo(photos, url, sort_index=sort_index)

    for picture in soup.select(
        ".announcement-gallery-container picture, "
        ".announcement-gallery picture, "
        ".announcement-photos picture"
    ):
        sort_index = len(photos)
        url = None
        for element in picture.select("[data-big], source, img"):
            url = _photo_from_attrs(element)
            if url:
                break
        _register_photo(photos, url, sort_index=sort_index)

    for meta in soup.find_all("meta", property="og:image"):
        url = _photo_from_attrs(meta)
        _register_photo(photos, url, sort_index=len(photos))

    if not photos:
        for img in soup.select(
            ".announcement-gallery img, .gallery img, .announcement-photos img"
        ):
            url = _photo_from_attrs(img)
            _register_photo(photos, url, sort_index=len(photos))

    ordered = [url for _, url in sorted(photos.values(), key=lambda item: item[0])]
    return normalize_photo_list(ordered)


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
        if text and len(text) > 10 and _looks_like_seller_description(text):
            return text

    return None


def _looks_like_seller_description(text: str) -> bool:
    from autoplius.listing_description import is_seller_description

    return is_seller_description(text)


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

    title = resolve_listing_title(title=title, url=url)

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
