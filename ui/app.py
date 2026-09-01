from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, abort, jsonify, render_template, request, Response

from scraper.config import Settings
from scraper.db import (
    count_scrape_runs,
    db_stats,
    default_db_path,
    fetch_listing,
    fetch_listings,
    fetch_scrape_runs,
    init_db,
    scrape_runs_analytics,
)
from scraper.s3_storage import get_s3_client
from ui.photo_urls import is_external_photo_url, photo_display_url, photo_display_urls
from autoplius.cities_lt import distance_from_vilnius_label, google_maps_url
from autoplius.translate import is_translation_error
from autoplius.engine_volume import engine_volume_from_listing
from autoplius.photo_urls import listing_photo_sets, normalize_photo_list, thumb_photo_url
from autoplius.price_display import price_lt_lines
from autoplius.price_rb import estimate_price_rb
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
PAGE_SIZE = 50
RUNS_PAGE_SIZE = 30
SETTINGS = Settings.from_env()
TAB_ALL = "all"
TAB_NO_VOLUME = "no_volume"
TAB_ARCHIVED = "archived"

app = Flask(__name__)
app.config["DATA_DIR"] = DEFAULT_DATA_DIR
app.config["DB_PATH"] = Path(os.environ.get("DB_PATH", default_db_path(DEFAULT_DATA_DIR)))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@app.template_filter("photo_full_list")
def photo_full_list_filter(urls: list[str] | None) -> list[str]:
    return normalize_photo_list(urls or [])


@app.template_filter("photo_thumb_list")
def photo_thumb_list_filter(urls: list[str] | None) -> list[str]:
    return [url for url in (thumb_photo_url(item) for item in normalize_photo_list(urls or [])) if url]


@app.template_filter("listing_photos")
def listing_photos_filter(item: dict[str, Any]) -> dict[str, Any]:
    urls = item.get("photo_urls") or []
    if not urls and item.get("photo_url"):
        urls = [item["photo_url"]]
    sets = listing_photo_sets(urls)
    full = photo_display_urls(sets["full"])
    thumb = photo_display_urls(sets["thumb"])
    return {
        "full": full,
        "thumb": thumb,
        "cover_full": full[0] if full else None,
        "cover_thumb": thumb[0] if thumb else None,
    }


@app.template_filter("format_datetime")
def format_datetime(value: str | None) -> str:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return "—" if not value else value[:16].replace("T", " ")
    return dt.strftime("%d.%m.%Y %H:%M")


@app.template_filter("format_date")
def format_date(value: str | None) -> str:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return "—" if not value else value[:10]
    return dt.strftime("%d.%m.%Y")


@app.template_filter("format_time")
def format_time(value: str | None) -> str:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


@app.template_filter("format_duration")
def format_duration(value: float | int | None) -> str:
    if value is None:
        return "—"
    total = int(round(float(value)))
    if total < 60:
        return f"{total}с"
    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}м {seconds:02d}с"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}ч {minutes:02d}м"


@app.template_filter("engine_volume")
def engine_volume(item: dict[str, Any]) -> str:
    return engine_volume_from_listing(item) or "—"


@app.template_filter("price_rb")
def price_rb(item: dict[str, Any]):
    return estimate_price_rb(item)


@app.template_filter("photo_src")
def photo_src(url: str | None) -> str:
    return photo_display_url(url) or ""


@app.template_filter("photo_srcs")
def photo_srcs(urls: list[str] | None) -> list[str]:
    return photo_display_urls(urls)


@app.template_filter("price_lt_lines")
def price_lt_lines_filter(item: dict[str, Any]) -> list[tuple[str, str]]:
    return price_lt_lines(item)


@app.template_filter("price_rb_usd")
def price_rb_usd(item: dict[str, Any]) -> str:
    breakdown = estimate_price_rb(item)
    if breakdown is None:
        return "—"
    return breakdown.total_formatted


@app.template_filter("city_distance")
def city_distance(city: str | None) -> str:
    return distance_from_vilnius_label(city) or ""


@app.template_filter("city_maps_url")
def city_maps_url(city: str | None) -> str:
    return google_maps_url(city) or ""


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


def _clean_listing_title(value: str | None) -> str:
    if not value:
        return "—"
    cleaned = _LISTING_ID_SUFFIX_RE.sub("", value).strip().rstrip(",").strip()
    return cleaned or value.strip()


def _strip_body_type_from_title(title: str, body_type: str | None) -> str:
    if not title or title == "—":
        return title
    if body_type:
        title = re.sub(rf",\s*{re.escape(body_type)}\b", "", title, flags=re.I)
        title = re.sub(rf"\b{re.escape(body_type)}\s+", "", title, flags=re.I)
    # Drop LT/other body label before the year suffix, e.g. ", Universalas 2020-10 m."
    title = re.sub(
        r",\s*\S+\s+(?=\d{4}(?:-\d{2})?\s*m\.?\s*$)",
        ", ",
        title,
        flags=re.I,
    )
    return re.sub(r"\s{2,}", " ", title).strip().rstrip(",").strip()


def _strip_year_from_title(title: str, year: str | None) -> str:
    if not title or title == "—":
        return title
    if year:
        title = re.sub(rf",?\s*{re.escape(str(year).strip())}\s*m\.?\s*$", "", title, flags=re.I)
    title = re.sub(r",?\s*\d{4}(?:-\d{2})?\s*m\.?\s*$", "", title, flags=re.I)
    return title.strip().rstrip(",").strip()


def _strip_engine_from_title(title: str, engine: str | None) -> str:
    if not title or title == "—":
        return title
    if engine:
        engine_text = engine.strip()
        if engine_text:
            title = re.sub(rf",\s*{re.escape(engine_text)}\b", "", title, flags=re.I)
            title = re.sub(rf"\b{re.escape(engine_text)}\b", "", title, flags=re.I)
    title = re.sub(r",\s*\d+(?:[.,]\d+)?\s*l\.?\b", "", title, flags=re.I)
    return re.sub(r"\s{2,}", " ", title).strip().rstrip(",").strip()


@app.template_filter("listing_title")
def listing_title(value: str | None) -> str:
    return _clean_listing_title(value)


@app.template_filter("listing_headline")
def listing_headline(item: dict[str, Any]) -> str:
    title = _clean_listing_title(item.get("title"))
    title = _strip_body_type_from_title(title, (item.get("body_type") or "").strip())
    title = _strip_year_from_title(title, item.get("year"))
    return _strip_engine_from_title(title, item.get("engine"))


def _split_make_model(headline: str) -> tuple[str, str]:
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


@app.template_filter("listing_make_model")
def listing_make_model(item: dict[str, Any]) -> tuple[str, str]:
    return _split_make_model(listing_headline(item))


def _check_basic_auth() -> bool:
    user = (os.environ.get("UI_USER") or "").strip()
    password = (os.environ.get("UI_PASSWORD") or "").strip()
    if not user:
        return True
    auth = request.authorization
    return bool(auth and auth.username == user and auth.password == password)


@app.before_request
def require_auth():
    if _check_basic_auth():
        return None
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Autoplius Scraper"'},
    )


def db_path() -> Path:
    return Path(app.config["DB_PATH"])


def require_db() -> Path:
    path = db_path()
    if not path.is_file():
        abort(503, "SQLite database not found. Run import_to_db.py first.")
    init_db(path)
    return path


def thumb_url(item: dict[str, Any]) -> str | None:
    if item.get("photo_url"):
        return photo_display_url(item["photo_url"])
    photos = item.get("photo_urls") or []
    return photo_display_url(photos[0]) if photos else None


def _upto_19l_enabled() -> bool:
    if "upto_19l" not in request.args:
        return True
    return "1" in request.args.getlist("upto_19l")


def _passable_enabled() -> bool:
    if "passable" not in request.args:
        return False
    return "1" in request.args.getlist("passable")


def _over_3y_enabled() -> bool:
    if "over_3y" not in request.args:
        return True
    return "1" in request.args.getlist("over_3y")


def _selected_cities() -> list[str]:
    seen: set[str] = set()
    cities: list[str] = []
    for raw in request.args.getlist("city"):
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cities.append(name)
    return cities


def _city_options(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        (item.get("city") or "").strip()
        for item in listings
        if (item.get("city") or "").strip()
    )
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))
    ]


def _filter_by_cities(
    listings: list[dict[str, Any]],
    selected: list[str],
) -> list[dict[str, Any]]:
    if not selected:
        return listings
    allowed = set(selected)
    return [item for item in listings if (item.get("city") or "").strip() in allowed]


def _current_tab() -> str:
    tab = (request.args.get("tab") or TAB_ALL).strip()
    return tab if tab in {TAB_ALL, TAB_NO_VOLUME, TAB_ARCHIVED} else TAB_ALL


def _fetch_index_listings(
    path: Path,
    *,
    q: str,
    min_price: int | None,
    max_price: int | None,
    sort: str,
    tab: str,
    upto_19l: bool,
    passable: bool,
    over_3y: bool,
    lite: bool = False,
) -> list[dict[str, Any]]:
    common = dict(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        passable_only=passable,
        listing_status="archived" if tab == TAB_ARCHIVED else "active",
        older_than_3_only=over_3y,
    )
    if tab == TAB_NO_VOLUME:
        return fetch_listings(
            path,
            **common,
            engine_volume_missing=True,
            lite=lite,
        )
    return fetch_listings(
        path,
        **common,
        engine_upto_liters=1.9 if upto_19l else None,
        lite=lite,
    )


def _image_response(data: bytes, content_type: str) -> Response:
    return Response(
        data,
        mimetype=content_type,
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


@app.get("/media/object")
def media_object():
    key = request.args.get("key", "").strip()
    if not key or ".." in key or key.startswith("/"):
        abort(400, "Invalid object key")
    if not SETTINGS.s3_enabled:
        abort(503, "S3 storage is not configured")

    try:
        response = get_s3_client(SETTINGS).get_object(Bucket=SETTINGS.s3_bucket, Key=key)
    except (ClientError, BotoCoreError):
        abort(404, "Object not found")

    body = response.get("Body")
    if body is None:
        abort(404, "Object body missing")
    content_type = response.get("ContentType") or "application/octet-stream"
    return _image_response(body.read(), content_type)


@app.get("/media/proxy")
def media_proxy():
    url = request.args.get("url", "").strip()
    if not is_external_photo_url(url):
        abort(400, "Invalid photo URL")

    try:
        request_obj = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AutopliusScraper/1.0)",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": f"{SETTINGS.autoplius_base_url}/",
            },
        )
        with urlopen(request_obj, timeout=20) as response:
            data = response.read()
            content_type = (response.headers.get("Content-Type") or "image/jpeg").split(";")[0]
    except Exception:
        abort(502, "Failed to fetch image")

    if not data:
        abort(502, "Empty image response")
    return _image_response(data, content_type)


def display_description(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (primary_text, original_text) for description block."""
    original = item.get("description")
    translated = item.get("description_ru")
    if is_translation_error(translated):
        translated = None
    if translated:
        show_original = original if original and original != translated else None
        return translated, show_original
    return original, None


@app.get("/")
def index():
    path = require_db()
    q = request.args.get("q", "")
    sort = request.args.get("sort", "price_asc")
    upto_19l = _upto_19l_enabled()
    passable = _passable_enabled()
    over_3y = _over_3y_enabled()
    tab = _current_tab()
    page = max(1, int(request.args.get("page", "1") or "1"))
    min_price_raw = request.args.get("min_price", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    min_price = int(min_price_raw) if min_price_raw.isdigit() else None
    max_price = int(max_price_raw) if max_price_raw.isdigit() else None

    stats = db_stats(path)
    filtered = _fetch_index_listings(
        path,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        tab=tab,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
        lite=True,
    )
    selected_cities = _selected_cities()
    city_options = _city_options(filtered)
    filtered = _filter_by_cities(filtered, selected_cities)
    no_volume_count = (
        len(filtered)
        if tab == TAB_NO_VOLUME
        else None
    )

    total_in_db = int(stats.get("active_listings") or stats.get("listings") or 0)
    archived_count = int(stats.get("archived_listings") or 0)
    total_filtered = len(filtered)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    listings = filtered[start : start + PAGE_SIZE]

    return render_template(
        "index.html",
        listings=listings,
        total_in_db=total_in_db,
        archived_count=archived_count,
        total_filtered=total_filtered,
        enriched_count=int(stats.get("enriched") or 0),
        with_phone=int(stats.get("with_phone") or 0),
        with_vin=int(stats.get("with_vin") or 0),
        db_stats=stats,
        q=q,
        sort=sort,
        min_price=min_price_raw,
        max_price=max_price_raw,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
        selected_cities=selected_cities,
        city_options=city_options,
        tab=tab,
        active_tab=tab,
        no_volume_count=no_volume_count,
        page=page,
        pages=pages,
        page_size=PAGE_SIZE,
        thumb_url=thumb_url,
    )


@app.get("/analytics")
def analytics():
    path = require_db()
    page = max(1, int(request.args.get("page", "1") or "1"))
    total_runs = count_scrape_runs(path)
    pages = max(1, (total_runs + RUNS_PAGE_SIZE - 1) // RUNS_PAGE_SIZE)
    page = min(page, pages)
    offset = (page - 1) * RUNS_PAGE_SIZE

    runs = fetch_scrape_runs(path, limit=RUNS_PAGE_SIZE, offset=offset)
    no_volume_count = len(
        fetch_listings(path, engine_volume_missing=True, passable_only=False)
    )

    stats = db_stats(path)
    return render_template(
        "analytics.html",
        runs=runs,
        analytics=scrape_runs_analytics(path),
        db_stats=stats,
        archived_count=int(stats.get("archived_listings") or 0),
        total_runs=total_runs,
        page=page,
        pages=pages,
        active_tab="analytics",
        no_volume_count=no_volume_count,
    )


@app.get("/listing/<int:listing_id>")
def listing_detail(listing_id: int):
    item = fetch_listing(require_db(), listing_id)
    if item is None:
        abort(404, "listing not found in database")
    photos = listing_photos_filter(item)
    return render_template(
        "detail.html",
        item=item,
        photos=photos,
        display_description=display_description,
    )


@app.get("/api/listings")
def api_listings():
    path = require_db()
    q = request.args.get("q", "")
    sort = request.args.get("sort", "price_asc")
    upto_19l = _upto_19l_enabled()
    passable = _passable_enabled()
    over_3y = _over_3y_enabled()
    tab = _current_tab()
    min_price_raw = request.args.get("min_price", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    min_price = int(min_price_raw) if min_price_raw.isdigit() else None
    max_price = int(max_price_raw) if max_price_raw.isdigit() else None
    return jsonify(
        {
            "source": "sqlite",
            "stats": db_stats(path),
            "listings": _fetch_index_listings(
                path,
                q=q,
                min_price=min_price,
                max_price=max_price,
                sort=sort,
                tab=tab,
                upto_19l=upto_19l,
                passable=passable,
                over_3y=over_3y,
            ),
        }
    )


@app.get("/api/listings/<int:listing_id>")
def api_listing(listing_id: int):
    item = fetch_listing(require_db(), listing_id)
    if item is None:
        abort(404)
    return jsonify(item)


@app.get("/api/db/stats")
def api_db_stats():
    return jsonify(db_stats(require_db()))


@app.get("/api/runs")
def api_runs():
    path = require_db()
    page = max(1, int(request.args.get("page", "1") or "1"))
    limit = min(100, max(1, int(request.args.get("limit", str(RUNS_PAGE_SIZE)) or RUNS_PAGE_SIZE)))
    offset = (page - 1) * limit
    return jsonify(
        {
            "runs": fetch_scrape_runs(path, limit=limit, offset=offset),
            "analytics": scrape_runs_analytics(path),
            "total": count_scrape_runs(path),
            "page": page,
        }
    )


def main() -> None:
    host = os.environ.get("UI_HOST", "0.0.0.0")
    port = int(os.environ.get("UI_PORT", "8080"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
