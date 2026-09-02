from __future__ import annotations

from dataclasses import replace
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, redirect, render_template, request, Response, session, url_for

from scraper.config import Settings
from scraper.db import (
    count_scrape_runs,
    create_user,
    db_stats,
    default_db_path,
    fetch_engine_catalog,
    fetch_listing,
    fetch_listings,
    fetch_listings_by_ids,
    fetch_scrape_runs,
    fetch_user_favorite_ids,
    get_user_by_id,
    init_db,
    engine_catalog_missing_count,
    engine_catalog_new_count,
    scrape_runs_analytics,
    toggle_user_favorite,
    update_listing_admin,
    set_listing_archived,
    set_listing_engine_volume,
    set_listing_manual_electric,
    update_engine_catalog_entry,
    verify_user_password,
)
from scraper.listing_filter_options import fetch_listing_filter_options
from scraper.listing_query import count_listings, fetch_listing_ids
from scraper.listing_sql_filters import ListingFilters
from ui.media_serve import (
    LIST_THUMB_WIDTH,
    parse_width,
    serve_remote_photo,
    serve_s3_object,
    serve_s3_object_from_cache,
)
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
from autoplius.detail_display import detail_spec_rows
from autoplius.listing_description import seller_description
from autoplius.price_display import catalog_price_lines, price_lt_lines
from autoplius.engine_volume import (
    engine_volume_from_listing,
    parse_manual_volume_input,
)
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
    transmission_short_label,
)
from autoplius.import_presets import preset_links
from autoplius.price_rb import estimate_price_rb
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
PAGE_SIZE = 50
RUNS_PAGE_SIZE = 30
LISTINGS_VIEW_TABLE = "table"
LISTINGS_VIEW_CARDS = "cards"
SETTINGS = Settings.from_env()
TAB_ALL = "all"
TAB_NO_VOLUME = "no_volume"
TAB_ELECTRIC = "electric"
TAB_ARCHIVED = "archived"
TAB_ADMIN = "admin"
DEFAULT_LIST_SORT = "added_desc"
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


@app.context_processor
def inject_import_presets() -> dict[str, Any]:
    return {"import_presets": preset_links(url_for("index"))}


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
    return photo_display_urls(
        [url for url in (thumb_photo_url(item) for item in normalize_photo_list(urls or [])) if url],
        width=LIST_THUMB_WIDTH,
    )


@app.template_filter("listing_photos")
def listing_photos_filter(item: dict[str, Any]) -> dict[str, Any]:
    urls = item.get("photo_urls") or []
    if not urls and item.get("photo_url"):
        urls = [item["photo_url"]]
    sets = listing_photo_sets(urls)
    full = photo_display_urls(sets["full"])
    thumb = photo_display_urls(sets["thumb"], width=LIST_THUMB_WIDTH)
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
    return engine_volume_from_listing(item) or "—"


@app.template_filter("transmission_short")
def transmission_short(value: str | None) -> str:
    return transmission_short_label(value) or ""


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


def _check_admin_form_credentials(username: str, password: str) -> bool:
    admin_user, admin_password = _admin_credentials()
    if not admin_user:
        return False
    return username == admin_user and password == admin_password


def _is_admin() -> bool:
    return _check_admin_auth() or session.get("admin") is True


def _current_user() -> dict[str, Any] | None:
    raw_id = session.get("user_id")
    if raw_id is None:
        return None
    path = db_path()
    if not path.is_file():
        return None
    try:
        init_db(path)
        user = get_user_by_id(path, int(raw_id))
    except (TypeError, ValueError):
        user = None
    if user is None:
        session.pop("user_id", None)
        session.pop("username", None)
        return None
    return user


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
    return redirect(url_for("login", next=_current_request_path()))


@app.before_request
def require_cabinet_auth():
    if not request.path.startswith("/cabinet"):
        return None
    if _is_admin():
        return redirect(url_for("index", sort=DEFAULT_LIST_SORT))
    if _current_user() is not None:
        return None
    return redirect(url_for("login", next=_current_request_path()))


@app.context_processor
def inject_nav_helpers():
    return {
        "nav_sort": request.args.get("sort", DEFAULT_LIST_SORT),
        "request_path": _current_request_path(),
    }


@app.context_processor
def inject_admin():
    return {"is_admin": _is_admin()}


@app.context_processor
def inject_user():
    return {"current_user": _current_user()}


@app.context_processor
def inject_favorites():
    user = _current_user()
    if user is None:
        return {"favorite_listing_ids": set()}
    path = db_path()
    if not path.is_file():
        return {"favorite_listing_ids": set()}
    try:
        init_db(path)
        return {
            "favorite_listing_ids": set(
                fetch_user_favorite_ids(path, int(user["id"]))
            ),
        }
    except Exception:
        return {"favorite_listing_ids": set()}


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
_MIN_REGISTRATION_PASSWORD_LEN = 6


def _safe_redirect_target(raw: str | None) -> str:
    target = (raw or "").strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index", sort=DEFAULT_LIST_SORT)


def _validate_registration_fields(
    username: str,
    password: str,
    password_confirm: str,
    *,
    display_name: str = "",
) -> tuple[str | None, dict[str, str]]:
    values = {
        "username": username.strip(),
        "display_name": display_name.strip(),
    }
    normalized = values["username"]
    if not normalized:
        return "Введите логин.", values
    if not _USERNAME_RE.fullmatch(normalized):
        return (
            "Логин: от 3 до 32 символов, только латиница, цифры, «_» и «-».",
            values,
        )
    admin_user, _admin_password = _admin_credentials()
    if admin_user and normalized.casefold() == admin_user.casefold():
        return "Этот логин зарезервирован.", values
    if len(password) < _MIN_REGISTRATION_PASSWORD_LEN:
        return f"Пароль: минимум {_MIN_REGISTRATION_PASSWORD_LEN} символов.", values
    if password != password_confirm:
        return "Пароли не совпадают.", values
    return None, values


def _current_request_path() -> str:
    qs = request.query_string.decode()
    return request.path + (f"?{qs}" if qs else "")


def _wants_json_response() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@app.get("/admin/enter")
def admin_enter():
    return redirect(url_for("login", next=_safe_redirect_target(request.args.get("next"))))


@app.get("/admin/logout")
def admin_logout():
    return redirect(url_for("logout"))


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next")
    if request.method == "GET":
        if _is_admin():
            return redirect(_safe_redirect_target(next_url or url_for("index", sort=DEFAULT_LIST_SORT)))
        if _current_user() is not None:
            return redirect(_safe_redirect_target(next_url or url_for("cabinet")))

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_url = request.form.get("next") or next_url
        if not username or not password:
            error = "Введите логин и пароль."
        elif _check_admin_form_credentials(username, password):
            session.permanent = True
            session["admin"] = True
            session.pop("user_id", None)
            session.pop("username", None)
            return redirect(_safe_redirect_target(next_url or url_for("index", sort=DEFAULT_LIST_SORT)))
        else:
            try:
                user = verify_user_password(require_db(), username, password)
            except Exception:
                user = None
            if user is None:
                error = "Неверный логин или пароль."
            else:
                session.permanent = True
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session.pop("admin", None)
                return redirect(_safe_redirect_target(next_url or url_for("cabinet")))

    return render_template("login.html", error=error, next=next_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    if _is_admin():
        return redirect(url_for("index", sort=DEFAULT_LIST_SORT))
    if _current_user() is not None:
        return redirect(url_for("cabinet"))

    error = None
    values = {"username": "", "display_name": ""}
    if request.method == "POST":
        username = request.form.get("username") or ""
        password = request.form.get("password") or ""
        password_confirm = request.form.get("password_confirm") or ""
        display_name = request.form.get("display_name") or ""
        error, values = _validate_registration_fields(
            username,
            password,
            password_confirm,
            display_name=display_name,
        )
        if error is None:
            try:
                user = create_user(
                    require_db(),
                    values["username"],
                    password,
                    display_name=values["display_name"] or None,
                )
            except ValueError as exc:
                message = str(exc)
                if "already exists" in message:
                    error = "Пользователь с таким логином уже существует."
                elif "username must be at least" in message:
                    error = "Логин: минимум 3 символа."
                elif "password required" in message:
                    error = "Введите пароль."
                else:
                    error = "Не удалось создать аккаунт. Попробуйте другой логин."
            else:
                session.permanent = True
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session.pop("admin", None)
                return redirect(url_for("cabinet"))

    return render_template("register.html", error=error, values=values)


@app.get("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("admin", None)
    return redirect(url_for("index", tab=TAB_ALL, sort=DEFAULT_LIST_SORT))


@app.get("/cabinet")
def cabinet():
    user = _current_user()
    if user is None:
        return redirect(url_for("login", next=url_for("cabinet")))
    path = require_db()
    stats = db_stats(path)
    favorite_ids = fetch_user_favorite_ids(path, int(user["id"]))
    favorites = fetch_listings_by_ids(path, favorite_ids, lite=False)
    return render_template(
        "cabinet.html",
        user=user,
        stats=stats,
        favorites=favorites,
        favorites_count=len(favorites),
        tab=TAB_ALL,
    )


@app.post("/favorites/<int:listing_id>")
def toggle_favorite(listing_id: int):
    user = _current_user()
    if user is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "login required"}), 401
        return redirect(url_for("login", next=_current_request_path()))
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "not found"}), 404
        abort(404, "listing not found in database")
    favorited = toggle_user_favorite(path, int(user["id"]), listing_id)
    if _wants_json_response():
        return jsonify({"ok": True, "id": listing_id, "favorited": favorited})
    next_url = _safe_redirect_target(
        request.form.get("next") or request.args.get("next")
    )
    return redirect(next_url)


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
            "electric_count": count_listings(
                path,
                ListingFilters(electric_only=True, catalog_filter=False),
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
    return tab if tab in {TAB_ALL, TAB_NO_VOLUME, TAB_ELECTRIC, TAB_ARCHIVED} else TAB_ALL


def _current_listings_view() -> str:
    view = (request.args.get("view") or LISTINGS_VIEW_TABLE).strip()
    return view if view in {LISTINGS_VIEW_TABLE, LISTINGS_VIEW_CARDS} else LISTINGS_VIEW_TABLE


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
        electric_only=tab == TAB_ELECTRIC,
        engine_upto_liters=1.9 if upto_19l and tab not in {TAB_NO_VOLUME, TAB_ELECTRIC} else None,
        catalog_filter=tab not in {TAB_NO_VOLUME, TAB_ELECTRIC},
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
    filters = _listing_filters_for_tab(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        tab=tab,
        upto_19l=upto_19l,
        passable=passable,
        over_3y=over_3y,
    )
    ids = fetch_listing_ids(path, filters)
    return fetch_listings_by_ids(path, ids, lite=lite)


@app.get("/media/object")
def media_object():
    key = request.args.get("key", "").strip()
    if not key or ".." in key or key.startswith("/"):
        abort(400, "Invalid object key")
    width = parse_width(request.args.get("w"))
    if SETTINGS.s3_enabled:
        return serve_s3_object(SETTINGS, key, width)
    return serve_s3_object_from_cache(key, width)


@app.get("/media/proxy")
def media_proxy():
    url = request.args.get("url", "").strip()
    if not is_external_photo_url(url):
        abort(400, "Invalid photo URL")
    return serve_remote_photo(url, SETTINGS.autoplius_base_url, parse_width(request.args.get("w")))


def display_description(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (primary_text, original_text) for description block."""
    return seller_description(item)


@app.template_filter("detail_spec_rows")
def detail_spec_rows_filter(item: dict[str, Any]) -> list[dict[str, str]]:
    return detail_spec_rows(item)


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
    sort = request.args.get("sort", DEFAULT_LIST_SORT)
    upto_19l = _upto_19l_enabled()
    passable = _passable_enabled()
    over_3y = _over_3y_enabled()
    tab = _current_tab()
    listings_view = _current_listings_view()
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

    no_volume_count = count_listings(
        path, ListingFilters(engine_volume_missing=True, catalog_filter=False)
    )
    electric_count = count_listings(
        path, ListingFilters(electric_only=True, catalog_filter=False)
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
        electric_count=electric_count,
        page=page,
        pages=pages,
        page_size=PAGE_SIZE,
        listings_view=listings_view,
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


@app.post("/api/listings/<int:listing_id>/engine-volume")
def api_listing_engine_volume(listing_id: int):
    if not _is_admin():
        return jsonify({"ok": False, "error": "admin required"}), 403
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        return jsonify({"ok": False, "error": "not found"}), 404

    payload = request.get_json(silent=True) or {}
    raw = payload.get("liters", payload.get("volume", request.form.get("liters")))
    liters = parse_manual_volume_input(str(raw) if raw is not None else None)
    if liters is None:
        return jsonify({"ok": False, "error": "invalid volume"}), 400

    updated = set_listing_engine_volume(path, listing_id, liters)
    if updated is None:
        return jsonify({"ok": False, "error": "not found"}), 404

    invalidate_catalog_cache()
    return jsonify({"ok": True, "id": listing_id, "liters": liters})


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
        back_url=_safe_redirect_target(request.args.get("next")),
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
    if tab not in {TAB_ALL, TAB_NO_VOLUME, TAB_ELECTRIC, TAB_ARCHIVED}:
        tab = TAB_ALL
    return redirect(url_for("index", tab=tab, **params))


@app.post("/admin/listings/<int:listing_id>/archive")
def admin_archive_listing(listing_id: int):
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "not found"}), 404
        abort(404, "listing not found in database")
    set_listing_archived(path, listing_id, archived=True)
    if _wants_json_response():
        return jsonify({"ok": True, "id": listing_id, "archived": True})
    return _admin_listing_redirect(archived=1)


@app.post("/admin/listings/<int:listing_id>/restore")
def admin_restore_listing(listing_id: int):
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "not found"}), 404
        abort(404, "listing not found in database")
    set_listing_archived(path, listing_id, archived=False)
    if _wants_json_response():
        return jsonify({"ok": True, "id": listing_id, "archived": False})
    return _admin_listing_redirect(restored=1)


@app.post("/admin/listings/<int:listing_id>/mark-electric")
def admin_mark_electric(listing_id: int):
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "not found"}), 404
        abort(404, "listing not found in database")
    updated = set_listing_manual_electric(path, listing_id, enabled=True)
    if updated is None:
        if _wants_json_response():
            return jsonify({"ok": False, "error": "not found"}), 404
        abort(404, "listing not found in database")
    if _wants_json_response():
        return jsonify({"ok": True, "id": listing_id, "manual_electric": True})
    return _admin_listing_redirect(marked_electric=1)


@app.post("/api/listings/<int:listing_id>/mark-electric")
def api_listing_mark_electric(listing_id: int):
    if not _is_admin():
        return jsonify({"ok": False, "error": "admin required"}), 403
    path = require_db()
    if fetch_listing(path, listing_id) is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    updated = set_listing_manual_electric(path, listing_id, enabled=True)
    if updated is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "id": listing_id, "manual_electric": True})


@app.get("/api/listings")
def api_listings():
    path = require_db()
    q = request.args.get("q", "")
    sort = request.args.get("sort", DEFAULT_LIST_SORT)
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
