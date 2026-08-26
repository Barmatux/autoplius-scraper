from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, Response

from scraper.db import db_stats, default_db_path, fetch_listing, fetch_listings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
PAGE_SIZE = 50

app = Flask(__name__)
app.config["DATA_DIR"] = DEFAULT_DATA_DIR
app.config["DB_PATH"] = Path(os.environ.get("DB_PATH", default_db_path(DEFAULT_DATA_DIR)))


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
    return path


def thumb_url(item: dict[str, Any]) -> str | None:
    if item.get("photo_url"):
        return item["photo_url"]
    photos = item.get("photo_urls") or []
    return photos[0] if photos else None


@app.get("/")
def index():
    path = require_db()
    q = request.args.get("q", "")
    sort = request.args.get("sort", "price_asc")
    # Show ALL listings by default; optional filter for enriched only.
    details_only = request.args.get("details_only") == "1"
    page = max(1, int(request.args.get("page", "1") or "1"))
    min_price_raw = request.args.get("min_price", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    min_price = int(min_price_raw) if min_price_raw.isdigit() else None
    max_price = int(max_price_raw) if max_price_raw.isdigit() else None

    stats = db_stats(path)
    filtered = fetch_listings(
        path,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        details_only=details_only,
    )

    total_in_db = int(stats.get("listings") or 0)
    total_filtered = len(filtered)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    listings = filtered[start : start + PAGE_SIZE]

    return render_template(
        "index.html",
        listings=listings,
        total_in_db=total_in_db,
        total_filtered=total_filtered,
        enriched_count=int(stats.get("enriched") or 0),
        with_phone=int(stats.get("with_phone") or 0),
        with_vin=int(stats.get("with_vin") or 0),
        db_stats=stats,
        q=q,
        sort=sort,
        min_price=min_price_raw,
        max_price=max_price_raw,
        details_only=details_only,
        page=page,
        pages=pages,
        page_size=PAGE_SIZE,
        thumb_url=thumb_url,
    )


@app.get("/listing/<int:listing_id>")
def listing_detail(listing_id: int):
    item = fetch_listing(require_db(), listing_id)
    if item is None:
        abort(404, "listing not found in database")
    return render_template("detail.html", item=item)


@app.get("/api/listings")
def api_listings():
    path = require_db()
    q = request.args.get("q", "")
    sort = request.args.get("sort", "price_asc")
    details_only = request.args.get("details_only") == "1"
    min_price_raw = request.args.get("min_price", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    min_price = int(min_price_raw) if min_price_raw.isdigit() else None
    max_price = int(max_price_raw) if max_price_raw.isdigit() else None
    return jsonify(
        {
            "source": "sqlite",
            "stats": db_stats(path),
            "listings": fetch_listings(
                path,
                q=q,
                min_price=min_price,
                max_price=max_price,
                sort=sort,
                details_only=details_only,
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


def main() -> None:
    host = os.environ.get("UI_HOST", "0.0.0.0")
    port = int(os.environ.get("UI_PORT", "8080"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
