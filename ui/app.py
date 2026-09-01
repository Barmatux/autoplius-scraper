from __future__ import annotations

from dataclasses import replace
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, abort, jsonify, redirect, render_template, request, Response, session, url_for

from scraper.config import Settings
from scraper.db import (
    count_scrape_runs,
    db_stats,
    default_db_path,
    fetch_engine_catalog,
    fetch_listing,
    fetch_listings,
    fetch_listings_by_ids,
    fetch_scrape_runs,
    init_db,
    engine_catalog_missing_count,
    engine_catalog_new_count,
    scrape_runs_analytics,
    update_listing_admin,
    set_listing_archived,
    update_engine_catalog_entry,
)
from scraper.listing_filter_options import fetch_listing_filter_options
from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters
from scraper.s3_storage import get_s3_client
from ui.photo_urls import is_external_photo_url, photo_display_url, photo_display_urls
from ui.table_layout import COL_KEYS, load_table_layout, save_table_layout, validate_layout
from autoplius.cities_lt import distance_from_vilnius_label, google_maps_url
from autoplius.engine_catalog import (
    catalog_stats,
    configure_catalog_db,
    filter_catalog_entries_upto_liters,
    invalidate_catalog_cache,
    refresh_engine_catalog,
    split_catalog_entries,
)
from autoplius.translate import is_translation_error
from autoplius.engine_volume import engine_volume_from_listing
from autoplius.photo_urls import listing_photo_sets, normalize_photo_list, thumb_photo_url
from autoplius.listing_display import clean_listing_title, listing_headline as display_listing_headline
from autoplius.listing_display import listing_make_model as parse_listing_make_model
from autoplius.make_model_filters import (
    build_make_model_options,
    build_year_options,
    exclude_blocked_makes,
    filter_by_vehicle_rows,
    filter_by_year,
    parse_optional_year,
    parse_vehicle_filter_rows,
    sanitize_vehicle_rows,
)
from autoplius.spec_filters import (
    build_spec_filter_options,
    build_transmission_raw_values,
    filter_by_body_types,
    filter_by_fuel_types,
    filter_by_transmissions,
    filter_by_volume_range,
    parse_multi_param_values,
    parse_volume_param,
)
from autoplius.transmission_labels import (
    parse_transmission_filter_values,
    transmission_db_values_for_slugs,
)
from autoplius.price_display import catalog_price_lines, price_lt_lines
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
TAB_ADMIN = "admin"
ADMIN_PAGE_SIZE = 50

app = Flask(__name__)
app.config["DATA_DIR"] = DEFAULT_DATA_DIR
app.config["DB_PATH"] = Path(os.environ.get("DB_PATH", default_db_path(DEFAULT_DATA_DIR)))
app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("ADMIN_PASSWORD")
    or os.environ.get("UI_PASSWORD")
    or "autoplius-dev-secret-change-me"
)


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
        return "тАФ" if not value else value[:16].replace("T", " ")
    return dt.strftime("%d.%m.%Y %H:%M")


@app.template_filter("format_date")
def format_date(value: str | None) -> str:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return "тАФ" if not value else value[:10]
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
        return "тАФ"
    total = int(round(float(value)))
    if total < 60:
        return f"{total}╤Б"
    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}╨╝ {seconds:02d}╤Б"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}╤З {minutes:02d}╨╝"


@app.template_filter("engine_volume")
def engine_volume(item: dict[str, Any]) -> str:
    return engine_volume_from_listing(item) or "тАФ"


@app.template_filter("engine_kpp_lines")
def engine_kpp_lines(item: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    volume = engine_volume_from_listing(item)
    if volume:
        lines.append(volume.replace(" ╨╗", ""))
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


@app.template_filter("price_rb")
def price_rb(item: dict[str, Any]):
    return estimate_price_rb(item)


@app.template_filter("photo_src")
def photo_src(url: str | None) -> str:
    return photo_display_url(url) or ""


@app.template_filter("photo_srcs")
def photo_srcs(urls: list[str] | None) -> list[str]:
    return photo_display_urls(urls)


@app.template_filter("catalog_price_lines")
def catalog_price_lines_filter(item: dict[str, Any]):
    return catalog_price_lines(item)


@app.template_filter("price_lt_lines")
def price_lt_lines_filter(item: dict[str, Any]) -> list[tuple[str, str]]:
    return price_lt_lines(item)


@app.template_filter("price_rb_usd")
def price_rb_usd(item: dict[str, Any]) -> str:
    breakdown = estimate_price_rb(item)
    if breakdown is None:
        return "тАФ"
    return breakdown.total_formatted


@app.template_filter("city_distance")
def city_distance(city: str | None) -> str:
    return distance_from_vilnius_label(city) or ""


@app.template_filter("city_maps_url")
def city_maps_url(city: str | None) -> str:
    return google_maps_url(city) or ""


@app.template_filter("listing_title")
def listing_title(value: str | None) -> str:
    return clean_listing_title(value)


@app.template_filter("listing_headline")
def listing_headline_filter(item: dict[str, Any]) -> str:
    return display_listing_headline(item)


@app.template_filter("listing_make_model")
def listing_make_model_filter(item: dict[str, Any]) -> tuple[str, str]:
    return parse_listing_make_model(item)


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


def _admin_credentials() -> tuple[str, str]:
    user = (os.environ.get("ADMIN_USER") or os.environ.get("UI_USER") or "").strip()
    password = (os.environ.get("ADMIN_PASSWORD") or os.environ.get("UI_PASSWORD") or "").strip()
    return user, password


def _check_admin_auth() -> bool:
    user, password = _admin_credentials()
    if not user:
        return False
    auth = request.authorization
    return bool(auth and auth.username == user and auth.password == password)


def _is_admin() -> bool:
    return _check_admin_auth() or session.get("admin") is True


@app.before_request
def require_admin_auth():
    if not request.path.startswith("/admin"):
        return None
    if request.endpoint in {"admin_enter", "admin_logout"}:
        return None
    user, _password = _admin_credentials()
    if not user:
        abort(
            503,
            "Admin auth is not configured. Set ADMIN_USER and ADMIN_PASSWORD in .env",
        )
    if _is_admin():
        return None
    return Response(
        "Admin authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Autoplius Admin"'},
    )


@app.context_processor
def inject_admin():
    return {"is_admin": _is_admin()}


def _safe_redirect_target(raw: str | None) -> str:
    target = (raw or "").strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index")


@app.get("/admin/enter")
def admin_enter():
    user, _password = _admin_credentials()
    if not user:
        abort(
            503,
            "Admin auth is not configured. Set ADMIN_USER and ADMIN_PASSWORD in .env",
        )
    if not _check_admin_auth():
        return Response(
            "Admin authentication required",
            401,
            {"WWW-Authenticate": 'Basic realm="Autoplius Admin"'},
        )
    session.permanent = True
    session["admin"] = True
    return redirect(_safe_redirect_target(request.args.get("next")))


@app.get("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.context_processor
def inject_tab_counts():
    path = db_path()
    if not path.is_file():
        return {}
    try:
        init_db(path)
        return {
            "catalog_missing_count": engine_catalog_missing_count(path),
            "catalog_new_count": engine_catalog_new_count(path),
            "no_volume_count": count_listings(
                path,
                ListingFilters(engine_volume_missing=True, catalog_filter=False),
            ),
        }
    except Exception:
        return {}


def db_path() -> Path:
    return Path(app.config["DB_PATH"])


def require_db() -> Path:
    path = db_path()
    if not path.is_file():
        abort(503, "SQLite database not found. Run import_to_db.py first.")
    init_db(path)
    configure_catalog_db(path)
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




def _listing_filters_for_tab(
    *,
    q: str,
    min_price: int | None,
    max_price: int | None,
    sort: str,
    tab: str,
    upto_19l: bool,
    passable: bool,
    over_3y: bool,
) -> ListingFilters:
    return ListingFilters(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        listing_status="archived" if tab == TAB_ARCHIVED else "active",
        older_than_3_only=over_3y,
        passable_only=passable,
        engine_volume_missing=tab == TAB_NO_VOLUME,
        engine_upto_liters=1.9 if upto_19l and tab != TAB_NO_VOLUME else None,
        catalog_filter=tab != TAB_NO_VOLUME,
        exclude_blocked_makes=True,
    )

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
        listings = fetch_listings(
            path,
            **common,
            engine_volume_missing=True,
            lite=lite,
        )
    else:
        listings = fetch_listings(
            path,
            **common,
            engine_upto_liters=1.9 if upto_19l else None,
            lite=lite,
        )
    return exclude_blocked_makes(listings)


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


@app.template_filter("listing_description")
def listing_description(item: dict[str, Any]) -> str | None:
    primary, _ = display_description(item)
    if not primary:
        return None
    text = primary.strip()
    return text or None

@app.template_filter("detail_scrape_pending")
def detail_scrape_pending(item: dict[str, Any]) -> bool:
    return bool(item) and not bool(item.get("detail_scraped"))


@app.template_filter("detail_error_public")
def detail_error_public(item: dict[str, Any]) -> str | None:
    if not item:
        return None
    error = (item.get("detail_error") or "").strip()
    return error or None


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
    base_filters = _listing_filters_for_tab(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        tab=tab,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
    )
    vehicle_rows = parse_vehicle_filter_rows(
        [value.strip() for value in request.args.getlist("make")],
        [value.strip() for value in request.args.getlist("model")],
    )
    year_from = parse_optional_year(request.args.get("year_from"))
    year_to = parse_optional_year(request.args.get("year_to"))
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from

    base_options = fetch_listing_filter_options(path, base_filters)
    make_model_options = base_options.make_model_options
    year_options = base_options.year_options
    vehicle_rows = sanitize_vehicle_rows(vehicle_rows, make_model_options)

    selected_cities = _selected_cities()
    selected_body_types = parse_multi_param_values(request.args.getlist("body_type"))
    selected_fuels = parse_multi_param_values(request.args.getlist("fuel"))
    selected_transmissions = parse_transmission_filter_values(request.args.getlist("transmission"))
    volume_from_str = request.args.get("volume_from", "").strip()
    volume_to_str = request.args.get("volume_to", "").strip()
    volume_from_raw = parse_volume_param(volume_from_str)
    volume_to_raw = parse_volume_param(volume_to_str)
    if volume_from_raw is not None and volume_to_raw is not None and volume_from_raw > volume_to_raw:
        volume_from_raw, volume_to_raw = volume_to_raw, volume_from_raw
        volume_from_str, volume_to_str = volume_to_str, volume_from_str

    city_options = base_options.city_options
    vehicle_year_filters = replace(
        base_filters,
        vehicle_rows=vehicle_rows,
        year_from=year_from,
        year_to=year_to,
    )
    has_vehicle_year = (
        year_from is not None
        or year_to is not None
        or any(
            (row.get("make") or "").strip() or (row.get("model") or "").strip()
            for row in vehicle_rows
        )
    )
    spec_options = (
        fetch_listing_filter_options(path, vehicle_year_filters)
        if has_vehicle_year
        else base_options
    )
    spec_filters = spec_options.spec_filters(
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
    )
    transmission_values = transmission_db_values_for_slugs(
        spec_options.transmission_values,
        selected_transmissions,
    )

    selected_filters = replace(
        vehicle_year_filters,
        cities=selected_cities,
        body_types=selected_body_types,
        fuels=selected_fuels,
        transmissions=transmission_values,
        volume_from=volume_from_raw,
        volume_to=volume_to_raw,
    )

    no_volume_count = (
        count_listings(path, ListingFilters(engine_volume_missing=True, catalog_filter=False))
        if tab == TAB_NO_VOLUME
        else None
    )

    total_in_db = int(stats.get("active_listings") or stats.get("listings") or 0)
    archived_count = int(stats.get("archived_listings") or 0)
    total_filtered = count_listings(path, selected_filters)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    page_ids = fetch_listing_ids(
        path,
        selected_filters,
        limit=PAGE_SIZE,
        offset=start,
    )
    listings = fetch_listings_by_ids(path, page_ids, lite=True)

    return render_template(
        "index.html",
        listings=listings,
        table_layout=load_table_layout(app.config["DATA_DIR"]),
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
        selected_body_types=selected_body_types,
        selected_fuels=selected_fuels,
        selected_transmissions=selected_transmissions,
        spec_filters=spec_filters,
        volume_from=volume_from_str,
        volume_to=volume_to_str,
        city_options=city_options,
        vehicle_rows=vehicle_rows,
        make_model_options=make_model_options,
        year_options=year_options,
        year_from=year_from if year_from is not None else "",
        year_to=year_to if year_to is not None else "",
        tab=tab,
        active_tab=tab,
        no_volume_count=no_volume_count,
        page=page,
        pages=pages,
        page_size=PAGE_SIZE,
        thumb_url=thumb_url,
    )


@app.get("/api/table-layout")
def get_table_layout_api():
    layout = load_table_layout(app.config["DATA_DIR"])
    if layout is None:
        return jsonify({"version": 1, "widths": None})
    return jsonify(layout)


@app.post("/api/table-layout")
def save_table_layout_api():
    body = request.get_json(silent=True) or {}
    widths = body.get("widths")
    if not isinstance(widths, dict):
        return jsonify({"error": "widths required"}), 400
    if not validate_layout({"widths": widths}):
        return jsonify({"error": f"widths must include: {', '.join(COL_KEYS)}"}), 400
    saved = save_table_layout(app.config["DATA_DIR"], widths, source="ui")
    return jsonify(saved)


@app.get("/analytics")
def analytics():
    path = require_db()
    page = max(1, int(request.args.get("page", "1") or "1"))
    total_runs = count_scrape_runs(path)
    pages = max(1, (total_runs + RUNS_PAGE_SIZE - 1) // RUNS_PAGE_SIZE)
    page = min(page, pages)
    offset = (page - 1) * RUNS_PAGE_SIZE

    runs = fetch_scrape_runs(path, limit=RUNS_PAGE_SIZE, offset=offset)
    no_volume_count = count_listings(
        path,
        ListingFilters(engine_volume_missing=True, catalog_filter=False),
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


@app.get("/catalog")
def catalog():
    path = require_db()
    refresh_engine_catalog(path)
    invalidate_catalog_cache()

    q = request.args.get("q", "").strip()
    make_filter = request.args.get("make", "").strip()
    model_filter = request.args.get("model", "").strip()
    only_missing = request.args.get("missing") == "1"
    upto_19l = _upto_19l_enabled()

    entries = fetch_engine_catalog(path, q=q, make=make_filter, model=model_filter)
    if only_missing:
        entries = [entry for entry in entries if entry.get("customs_cm3") is None]
    entries = filter_catalog_entries_upto_liters(entries, enabled=upto_19l)
    catalog_sections = split_catalog_entries(entries)

    make_options = sorted({entry["make"] for entry in fetch_engine_catalog(path)}, key=str.casefold)
    model_options: list[str] = []
    if make_filter:
        model_options = sorted(
            {
                entry["model"]
                for entry in fetch_engine_catalog(path, make=make_filter)
            },
            key=str.casefold,
        )

    stats = db_stats(path)
    no_volume_count = count_listings(
        path,
        ListingFilters(engine_volume_missing=True, catalog_filter=False),
    )
    return render_template(
        "catalog.html",
        catalog_tree=catalog_sections["main_tree"],
        new_catalog_tree=catalog_sections["new_tree"],
        new_catalog_count=catalog_sections["new_count"],
        catalog_entries=entries,
        catalog_summary=catalog_stats(entries),
        q=q,
        make_filter=make_filter,
        model_filter=model_filter,
        only_missing=only_missing,
        upto_19l=upto_19l,
        make_options=make_options,
        model_options=model_options,
        db_stats=stats,
        archived_count=int(stats.get("archived_listings") or 0),
        active_tab="catalog",
        no_volume_count=no_volume_count,
    )


@app.post("/catalog/sync")
def catalog_sync():
    path = require_db()
    inserted, updated = refresh_engine_catalog(path)
    invalidate_catalog_cache()
    params: dict[str, Any] = {}
    for key in ("q", "make", "model"):
        value = (request.values.get(key) or "").strip()
        if value:
            params[key] = value
    if request.values.get("missing") == "1":
        params["missing"] = "1"
    if "upto_19l" in request.values:
        params["upto_19l"] = "1" if "1" in request.values.getlist("upto_19l") else "0"
    params["synced"] = inserted + updated
    params["inserted"] = inserted
    params["updated"] = updated
    return redirect(url_for("catalog", **params))


@app.post("/api/catalog/<int:entry_id>")
def api_catalog_update(entry_id: int):
    path = require_db()
    payload = request.get_json(silent=True) or {}
    raw_cm3 = payload.get("customs_cm3", request.form.get("customs_cm3"))
    notes = payload.get("notes", request.form.get("notes"))
    customs_cm3: int | None
    if raw_cm3 is None or str(raw_cm3).strip() == "":
        customs_cm3 = None
    else:
        try:
            customs_cm3 = int(str(raw_cm3).strip())
        except ValueError:
            return jsonify({"ok": False, "error": "invalid customs_cm3"}), 400
        if customs_cm3 <= 0:
            return jsonify({"ok": False, "error": "customs_cm3 must be positive"}), 400

    if not update_engine_catalog_entry(
        path,
        entry_id,
        customs_cm3=customs_cm3,
        notes=(str(notes).strip() if notes is not None else None),
    ):
        return jsonify({"ok": False, "error": "not found"}), 404

    invalidate_catalog_cache()
    return jsonify({"ok": True, "id": entry_id, "customs_cm3": customs_cm3, "is_new": customs_cm3 is None})


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


@app.get("/admin/listings")
def admin_listings():
    return redirect(url_for("index"))


@app.route("/admin/listings/<int:listing_id>/edit", methods=["GET", "POST"])
def admin_edit_listing(listing_id: int):
    path = require_db()
    item = fetch_listing(path, listing_id)
    if item is None:
        abort(404, "listing not found in database")

    error: str | None = None
    if request.method == "POST":
        patch, clear_overrides = _parse_admin_form()
        try:
            updated = update_listing_admin(
                path,
                listing_id,
                patch,
                clear_overrides=clear_overrides,
            )
        except ValueError as exc:
            error = str(exc)
            updated = None
        if updated is not None:
            return redirect(url_for("admin_edit_listing", listing_id=listing_id, saved=1))
        if error is None:
            error = "╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╤Б╨╛╤Е╤А╨░╨╜╨╕╤В╤М ╨╛╨▒╤К╤П╨▓╨╗╨╡╨╜╨╕╨╡"
        item = fetch_listing(path, listing_id) or item

    photos = listing_photos_filter(item)
    parameters_json = json.dumps(item.get("parameters") or {}, ensure_ascii=False, indent=2)
    photo_urls_text = "\n".join(item.get("photo_urls") or [])
    return render_template(
        "admin_edit.html",
        item=item,
        photos=photos,
        parameters_json=parameters_json,
        photo_urls_text=photo_urls_text,
        error=error,
        saved=request.args.get("saved") == "1",
        active_tab=_current_tab(),
        archived_count=int(db_stats(path).get("archived_listings") or 0),
        no_volume_count=count_listings(
            path,
            ListingFilters(engine_volume_missing=True, catalog_filter=False),
        ),
        back_url=_safe_redirect_target(request.args.get("next")),
    )


def _admin_listing_redirect(**params: str):
    tab = (request.form.get("tab") or request.args.get("tab") or TAB_ALL).strip()
    if tab not in {TAB_ALL, TAB_NO_VOLUME, TAB_ARCHIVED}:
        tab = TAB_ALL
    return redirect(url_for("index", tab=tab, **params))


@app.post("/admin/listings/<int:listing_id>/archive")
def admin_archive_listing(listing_id: int):
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        abort(404, "listing not found in database")
    set_listing_archived(path, listing_id, archived=True)
    return _admin_listing_redirect(archived=1)


@app.post("/admin/listings/<int:listing_id>/restore")
def admin_restore_listing(listing_id: int):
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        abort(404, "listing not found in database")
    set_listing_archived(path, listing_id, archived=False)
    return _admin_listing_redirect(restored=1)


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
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
