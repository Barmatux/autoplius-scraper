from __future__ import annotations

import os
from urllib.parse import urlencode, urlparse, urlunparse

DEFAULT_BASE_URL = "https://ru.autoplius.lt"
SEARCH_PATH = "/skelbimai/naudoti-automobiliai"

_configured_base: str | None = None


def configure_base_url(base_url: str) -> None:
    global _configured_base
    _configured_base = base_url.rstrip("/")


def get_base_url() -> str:
    if _configured_base:
        return _configured_base
    return os.environ.get("AUTOPLIUS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def build_search_url(
    *,
    page: int = 1,
    make_id: int | None = None,
    model_id: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    price_from: int | None = None,
    price_to: int | None = None,
    power_kw_to: int | None = None,
    extra: dict[str, str | int] | None = None,
    base_url: str | None = None,
) -> str:
    params: dict[str, str | int] = {"page_nr": page}
    if make_id is not None:
        params["make_id_list"] = make_id
    if model_id is not None:
        params["model_id_list"] = model_id
    if year_from is not None:
        params["make_date_from"] = year_from
    if year_to is not None:
        params["make_date_to"] = year_to
    if price_from is not None:
        params["sell_price_from"] = price_from
    if price_to is not None:
        params["sell_price_to"] = price_to
    if power_kw_to is not None:
        params["engine_power_to"] = power_kw_to
    if extra:
        params.update(extra)
    base = (base_url or get_base_url()).rstrip("/")
    return f"{base}{SEARCH_PATH}?{urlencode(params)}"


def normalize_listing_url(url: str, *, base_url: str | None = None) -> str:
    base = (base_url or get_base_url()).rstrip("/")
    clean = url.split("#", 1)[0].strip()
    if not clean:
        return base
    if clean.startswith("/"):
        return f"{base}{clean}"
    parsed = urlparse(clean)
    if not parsed.scheme:
        return f"{base}/{clean.lstrip('/')}"
    base_host = urlparse(base).netloc
    return urlunparse((parsed.scheme, base_host, parsed.path, "", parsed.query, ""))


def extract_listing_id(url: str) -> int | None:
    clean = url.split("#", 1)[0].split("?", 1)[0]
    if not clean.endswith(".html"):
        return None
    stem = clean.rsplit("/", 1)[-1].removesuffix(".html")
    tail = stem.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None
