#!/usr/bin/env python3
"""Add SQL page fetch + filter profile; wire index() to load photos only for current page."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
DB = ROOT / "scraper/db.py"
APP = ROOT / "ui/app.py"
NGINX = ROOT / "deploy/nginx-autoplius-ui.conf"


DB_MARKER = "def fetch_listings(\n"
DB_END_MARKER = "\n\ndef fetch_listing(db_path: Path, listing_id: int)"

DB_BLOCK = '''
LISTING_COLUMNS_FILTER = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, has_vin_badge, parameters_json, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)
LISTING_COLUMNS_LITE = (
    "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
    "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
    "city, photo_url, photo_urls_json, has_vin_badge, parameters_json, "
    "description, description_ru, "
    "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
)


def _listing_sort_sql(sort: str) -> str:
    return {
        "price_asc": "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur ASC",
        "price_desc": "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur DESC",
        "mileage_asc": "CASE WHEN mileage_km IS NULL THEN 1 ELSE 0 END, mileage_km ASC",
        "mileage_desc": "CASE WHEN mileage_km IS NULL THEN 1 ELSE 0 END, mileage_km DESC",
        "year_desc": "CASE WHEN year IS NULL THEN 1 ELSE 0 END, year DESC",
        "year_asc": "CASE WHEN year IS NULL THEN 1 ELSE 0 END, year ASC",
        "title_asc": "CASE WHEN title IS NULL THEN 1 ELSE 0 END, title ASC",
        "title_desc": "CASE WHEN title IS NULL THEN 1 ELSE 0 END, title DESC",
        "added_desc": "CASE WHEN first_seen_at IS NULL THEN 1 ELSE 0 END, first_seen_at DESC",
        "added_asc": "CASE WHEN first_seen_at IS NULL THEN 1 ELSE 0 END, first_seen_at ASC",
    }.get(sort, "CASE WHEN first_seen_at IS NULL THEN 1 ELSE 0 END, first_seen_at DESC")


def _listing_sql_filters(
    *,
    q: str,
    min_price: int | None,
    max_price: int | None,
    details_only: bool,
    listing_status: str,
) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if details_only:
        clauses.append("detail_scraped = 1")
    if listing_status == "active":
        clauses.append("(status IS NULL OR status = 'active')")
    elif listing_status == "archived":
        clauses.append("status = 'archived'")
    elif listing_status != "all":
        clauses.append("(status IS NULL OR status = 'active')")
    if min_price is not None:
        clauses.append("price_eur IS NOT NULL AND price_eur >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("price_eur IS NOT NULL AND price_eur <= ?")
        params.append(max_price)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        clauses.append(
            """(
                lower(COALESCE(title,'')) LIKE ?
                OR lower(COALESCE(city,'')) LIKE ?
                OR lower(COALESCE(fuel,'')) LIKE ?
                OR lower(COALESCE(phone,'')) LIKE ?
                OR lower(COALESCE(vin_masked,'')) LIKE ?
                OR lower(COALESCE(description,'')) LIKE ?
                OR lower(COALESCE(description_ru,'')) LIKE ?
                OR lower(COALESCE(parameters_json,'')) LIKE ?
                OR CAST(autoplius_id AS TEXT) LIKE ?
            )"""
        )
        params.extend([like] * 9)
    return clauses, params


def _listing_python_filters(
    listings: list[dict[str, Any]],
    *,
    engine_upto_liters: float | None,
    engine_volume_missing: bool,
    passable_only: bool,
    older_than_3_only: bool,
    catalog_filter: bool,
) -> list[dict[str, Any]]:
    if engine_volume_missing:
        listings = [
            item for item in listings if engine_volume_liters(item) is None
        ]
    elif engine_upto_liters is not None:
        listings = [
            item
            for item in listings
            if (liters := engine_volume_liters(item)) is not None
            and liters <= engine_upto_liters
        ]
    if passable_only:
        listings = [item for item in listings if is_passable_age(item)]
    if older_than_3_only:
        listings = [item for item in listings if is_older_than_years(item, years=3)]
    if catalog_filter:
        listings = [item for item in listings if is_catalog_visible(item)]
    return listings


def _listing_columns(*, lite: bool = False, profile: str | None = None) -> str:
    if profile == "filter":
        return LISTING_COLUMNS_FILTER
    if profile in {"page", "lite"} or lite:
        return LISTING_COLUMNS_LITE
    return "*"


def fetch_listings(
    db_path: Path,
    *,
    q: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "added_desc",
    details_only: bool = False,
    engine_upto_liters: float | None = None,
    engine_volume_missing: bool = False,
    passable_only: bool = False,
    listing_status: str = "active",
    older_than_3_only: bool = False,
    lite: bool = False,
    profile: str | None = None,
    catalog_filter: bool = True,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []

    clauses, params = _listing_sql_filters(
        q=q,
        min_price=min_price,
        max_price=max_price,
        details_only=details_only,
        listing_status=listing_status,
    )
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = _listing_columns(lite=lite, profile=profile)
    sql = f"SELECT {columns} FROM listings {where} ORDER BY {_listing_sort_sql(sort)}"
    query_params = list(params)
    if limit is not None:
        sql += " LIMIT ?"
        query_params.append(int(limit))
        if offset is not None:
            sql += " OFFSET ?"
            query_params.append(int(offset))

    with connect(db_path) as conn:
        rows = conn.execute(sql, query_params).fetchall()
        listings = [row_to_listing(r) for r in rows]

    return _listing_python_filters(
        listings,
        engine_upto_liters=engine_upto_liters,
        engine_volume_missing=engine_volume_missing,
        passable_only=passable_only,
        older_than_3_only=older_than_3_only,
        catalog_filter=catalog_filter,
    )


def fetch_listings_by_ids(
    db_path: Path,
    listing_ids: list[int],
    *,
    lite: bool = True,
) -> list[dict[str, Any]]:
    if not listing_ids or not db_path.is_file():
        return []

    columns = _listing_columns(lite=lite, profile="page" if lite else None)
    placeholders = ",".join("?" for _ in listing_ids)
    order_cases = " ".join(f"WHEN ? THEN {idx}" for idx in range(len(listing_ids)))
    sql = (
        f"SELECT {columns} FROM listings "
        f"WHERE autoplius_id IN ({placeholders}) "
        f"ORDER BY CASE autoplius_id {order_cases} END"
    )
    params = [*listing_ids, *listing_ids]

    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_listing(r) for r in rows]
'''


def patch_db(text: str) -> str:
    if "fetch_listings_by_ids" in text:
        print("db.py already patched")
        return text
    start = text.index(DB_MARKER)
    end = text.index(DB_END_MARKER, start)
    return text[:start] + DB_BLOCK.strip() + text[end:]


def patch_app(text: str) -> str:
    if "fetch_listings_by_ids" in text:
        print("app.py imports already patched")
    else:
        text = text.replace(
            "    fetch_listings,\n",
            "    fetch_listings,\n    fetch_listings_by_ids,\n",
            1,
        )

    old_fetch = """    lite: bool = False,
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
    return exclude_blocked_makes(listings)"""

    new_fetch = """    profile: str | None = None,
) -> list[dict[str, Any]]:
    common = dict(
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        passable_only=passable,
        listing_status="archived" if tab == TAB_ARCHIVED else "active",
        older_than_3_only=over_3y,
        profile=profile,
    )
    if tab == TAB_NO_VOLUME:
        listings = fetch_listings(
            path,
            **common,
            engine_volume_missing=True,
        )
    else:
        listings = fetch_listings(
            path,
            **common,
            engine_upto_liters=1.9 if upto_19l else None,
        )
    return exclude_blocked_makes(listings)"""

    if old_fetch not in text:
        raise SystemExit("_fetch_index_listings block not found")
    text = text.replace(old_fetch, new_fetch, 1)

    old_index = """        lite=True,
    )
    vehicle_rows = parse_vehicle_filter_rows("""

    new_index = """        profile="filter",
    )
    vehicle_rows = parse_vehicle_filter_rows("""

    if old_index not in text:
        raise SystemExit("index() fetch block not found")
    text = text.replace(old_index, new_index, 1)

    old_page = """    start = (page - 1) * PAGE_SIZE
    listings = filtered[start : start + PAGE_SIZE]

    template_context = dict(
        listings=listings,"""

    new_page = """    start = (page - 1) * PAGE_SIZE
    page_ids = [item["autoplius_id"] for item in filtered[start : start + PAGE_SIZE]]
    listings = fetch_listings_by_ids(path, page_ids, lite=True)

    template_context = dict(
        listings=listings,"""

    if old_page not in text:
        raise SystemExit("index() pagination block not found")
    return text.replace(old_page, new_page, 1)


NGINX_CONTENT = """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 256;
    gzip_types text/css application/javascript application/json text/plain text/xml application/xml;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
"""


def main() -> int:
    db_text = patch_db(DB.read_text(encoding="utf-8"))
    DB.write_text(db_text, encoding="utf-8")
    print("OK patched", DB)

    app_text = patch_app(APP.read_text(encoding="utf-8"))
    APP.write_text(app_text, encoding="utf-8")
    print("OK patched", APP)

    NGINX.write_text(NGINX_CONTENT, encoding="utf-8")
    print("OK wrote", NGINX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
