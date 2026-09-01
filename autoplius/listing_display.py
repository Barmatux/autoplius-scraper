from __future__ import annotations

import re
from typing import Any

from autoplius.listing_titles import is_invalid_listing_title, make_model_from_listing_url

_LISTING_ID_SUFFIX_RE = re.compile(r"\s*\|\s*A?\d+\s*$")

_MULTI_WORD_MAKES = (
    "Alfa Romeo",
    "Aston Martin",
    "Land Rover",
    "Range Rover",
    "Rolls-Royce",
    "Rolls Royce",
    "Great Wall",
    "Mercedes-Benz",
    "Mercedes Benz",
)


def clean_listing_title(value: str | None) -> str:
    if not value:
        return "—"
    cleaned = _LISTING_ID_SUFFIX_RE.sub("", value).strip().rstrip(",").strip()
    cleaned = cleaned or value.strip()
    if is_invalid_listing_title(cleaned):
        return "—"
    return cleaned


def strip_body_type_from_title(title: str, body_type: str | None) -> str:
    if not title or title == "—":
        return title
    if body_type:
        title = re.sub(rf",\s*{re.escape(body_type)}\b", "", title, flags=re.I)
        title = re.sub(rf"\b{re.escape(body_type)}\s+", "", title, flags=re.I)
    title = re.sub(
        r",\s*\S+\s+(?=\d{4}(?:-\d{2})?\s*m\.?\s*$)",
        ", ",
        title,
        flags=re.I,
    )
    return re.sub(r"\s{2,}", " ", title).strip().rstrip(",").strip()


def strip_year_from_title(title: str, year: str | None) -> str:
    if not title or title == "—":
        return title
    if year:
        title = re.sub(rf",?\s*{re.escape(str(year).strip())}\s*m\.?\s*$", "", title, flags=re.I)
    title = re.sub(r",?\s*\d{4}(?:-\d{2})?\s*m\.?\s*$", "", title, flags=re.I)
    return title.strip().rstrip(",").strip()


def strip_engine_from_title(title: str, engine: str | None) -> str:
    if not title or title == "—":
        return title
    if engine:
        engine_text = engine.strip()
        if engine_text:
            title = re.sub(rf",\s*{re.escape(engine_text)}\b", "", title, flags=re.I)
            title = re.sub(rf"\b{re.escape(engine_text)}\b", "", title, flags=re.I)
    title = re.sub(r",\s*\d+(?:[.,]\d+)?\s*l\.?\b", "", title, flags=re.I)
    return re.sub(r"\s{2,}", " ", title).strip().rstrip(",").strip()


def listing_headline(item: dict[str, Any]) -> str:
    title = (item.get("title") or "").strip()
    if is_invalid_listing_title(title):
        make, model = make_model_from_listing_url(item.get("url"))
        if make != "—":
            headline = f"{make} {model}".strip() if model else make
        else:
            listing_id = item.get("autoplius_id")
            headline = f"#{listing_id}" if listing_id else "—"
    else:
        headline = clean_listing_title(title)
    headline = strip_body_type_from_title(headline, (item.get("body_type") or "").strip())
    headline = strip_year_from_title(headline, item.get("year"))
    return strip_engine_from_title(headline, item.get("engine"))


def split_make_model(headline: str) -> tuple[str, str]:
    text = headline.strip().rstrip(".,").strip()
    if not text or text == "—":
        return "—", ""
    lower = text.casefold()
    for make in sorted(_MULTI_WORD_MAKES, key=len, reverse=True):
        prefix = make.casefold()
        if lower == prefix:
            return make, ""
        if lower.startswith(prefix + " "):
            model = text[len(make) :].strip(" .,")
            return make, model
    parts = text.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip(" .,")


def listing_make_model(item: dict[str, Any]) -> tuple[str, str]:
    return split_make_model(listing_headline(item))
