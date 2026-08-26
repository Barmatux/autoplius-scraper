from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, Response

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
PAGE_SIZE = 50

app = Flask(__name__)
app.config["DATA_DIR"] = DEFAULT_DATA_DIR


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


def data_dir() -> Path:
    return Path(app.config["DATA_DIR"])


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_snapshots() -> list[dict[str, Any]]:
    base = data_dir()
    items: list[dict[str, Any]] = []
    for mode in ("test", "prod"):
        snap_root = base / mode / "snapshots"
        if not snap_root.is_dir():
            continue
        for path in sorted(snap_root.rglob("*.json"), reverse=True):
            rel = path.relative_to(base).as_posix()
            stat = path.stat()
            items.append(
                {
                    "id": rel,
                    "mode": mode,
                    "name": path.name,
                    "date": path.parent.name,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
    return items


def resolve_snapshot(snapshot_id: str | None) -> Path:
    base = data_dir()
    if not snapshot_id or snapshot_id == "latest":
        return base / "latest.json"
    candidate = (base / snapshot_id).resolve()
    if not str(candidate).startswith(str(base.resolve())):
        abort(400, "invalid snapshot path")
    if not candidate.is_file():
        abort(404, "snapshot not found")
    return candidate


def filter_listings(
    listings: list[dict[str, Any]],
    *,
    q: str,
    min_price: int | None,
    max_price: int | None,
    sort: str,
    details_only: bool,
) -> list[dict[str, Any]]:
    q_norm = q.strip().lower()
    out: list[dict[str, Any]] = []
    for item in listings:
        if details_only and not item.get("detail_scraped"):
            continue
        if q_norm:
            params = item.get("parameters") or {}
            hay = " ".join(
                [
                    str(item.get(k) or "")
                    for k in (
                        "title",
                        "city",
                        "fuel",
                        "year",
                        "body_type",
                        "autoplius_id",
                        "phone",
                        "vin_masked",
                        "description",
                        "transmission",
                        "engine",
                    )
                ]
                + [f"{k} {v}" for k, v in params.items()]
            ).lower()
            if q_norm not in hay:
                continue
        price = item.get("price_eur")
        if min_price is not None and (price is None or price < min_price):
            continue
        if max_price is not None and (price is None or price > max_price):
            continue
        out.append(item)

    reverse = sort.endswith("_desc")
    key = sort.removesuffix("_asc").removesuffix("_desc")
    if key in {"price", "mileage", "year", "title"}:
        field = {
            "price": "price_eur",
            "mileage": "mileage_km",
            "year": "year",
            "title": "title",
        }[key]

        def sort_key(row: dict[str, Any]):
            val = row.get(field)
            if val is None:
                return (1, "")
            return (0, val)

        out.sort(key=sort_key, reverse=reverse)
    return out


def find_listing(payload: dict[str, Any], listing_id: int) -> dict[str, Any] | None:
    for item in payload.get("listings") or []:
        if item.get("autoplius_id") == listing_id:
            return item
    return None


def thumb_url(item: dict[str, Any]) -> str | None:
    if item.get("photo_url"):
        return item["photo_url"]
    photos = item.get("photo_urls") or []
    return photos[0] if photos else None


@app.get("/")
def index():
    snapshots = list_snapshots()
    snapshot_id = request.args.get("snapshot", "latest")
    q = request.args.get("q", "")
    sort = request.args.get("sort", "price_asc")
    details_only_raw = request.args.get("details_only")
    if not request.args:
        details_only = True
    else:
        details_only = details_only_raw == "1"
    page = max(1, int(request.args.get("page", "1") or "1"))
    min_price_raw = request.args.get("min_price", "").strip()
    max_price_raw = request.args.get("max_price", "").strip()
    min_price = int(min_price_raw) if min_price_raw.isdigit() else None
    max_price = int(max_price_raw) if max_price_raw.isdigit() else None

    path = resolve_snapshot(snapshot_id)
    payload = load_json(path) or {}
    all_listings = payload.get("listings") or []
    filtered = filter_listings(
        all_listings,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        details_only=details_only,
    )
    total_filtered = len(filtered)
    pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * PAGE_SIZE
    listings = filtered[start : start + PAGE_SIZE]
    last_run = load_json(data_dir() / "last_run.json") or {}

    enriched = sum(1 for x in all_listings if x.get("detail_scraped"))
    with_phone = sum(1 for x in all_listings if x.get("phone"))
    with_vin = sum(1 for x in all_listings if x.get("vin_masked"))

    return render_template(
        "index.html",
        snapshots=snapshots,
        snapshot_id=snapshot_id,
        payload=payload,
        listings=listings,
        total_in_snapshot=len(all_listings),
        total_filtered=total_filtered,
        enriched_count=enriched,
        with_phone=with_phone,
        with_vin=with_vin,
        last_run=last_run,
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
    snapshot_id = request.args.get("snapshot", "latest")
    path = resolve_snapshot(snapshot_id)
    payload = load_json(path) or {}
    item = find_listing(payload, listing_id)
    if item is None:
        abort(404, "listing not found in snapshot")
    return render_template(
        "detail.html",
        item=item,
        snapshot_id=snapshot_id,
        payload=payload,
    )


@app.get("/api/latest")
def api_latest():
    payload = load_json(data_dir() / "latest.json")
    if payload is None:
        abort(404)
    return jsonify(payload)


@app.get("/api/listings/<int:listing_id>")
def api_listing(listing_id: int):
    snapshot_id = request.args.get("snapshot", "latest")
    path = resolve_snapshot(snapshot_id)
    payload = load_json(path) or {}
    item = find_listing(payload, listing_id)
    if item is None:
        abort(404)
    return jsonify(item)


@app.get("/api/snapshots")
def api_snapshots():
    return jsonify(list_snapshots())


def main() -> None:
    host = os.environ.get("UI_HOST", "0.0.0.0")
    port = int(os.environ.get("UI_PORT", "8080"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
