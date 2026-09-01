from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from autoplius.engine_volume import engine_volume_liters
from autoplius.passable_age import is_older_than_years, is_passable_age
from autoplius.catalog_filters import is_catalog_visible
from autoplius.localize import localize_listing
from autoplius.photo_urls import normalize_photo_list
from scraper.listing_sync import (
    ADMIN_EDITABLE_FIELDS,
    LISTING_STATUS_ACTIVE,
    LISTING_STATUS_ARCHIVED,
    encode_manual_overrides,
    merge_listing_row,
    parse_manual_overrides,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_sec REAL,
    pages_scraped INTEGER,
    listing_count INTEGER,
    details_scraped INTEGER,
    details_failed INTEGER,
    enrich_details INTEGER,
    diff_new INTEGER,
    diff_removed INTEGER,
    diff_unchanged INTEGER,
    snapshot_path TEXT UNIQUE,
    page_stats_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    autoplius_id INTEGER PRIMARY KEY,
    url TEXT,
    title TEXT,
    year TEXT,
    body_type TEXT,
    price_eur INTEGER,
    price_net_eur INTEGER,
    price_gross_eur INTEGER,
    price_vat_note TEXT,
    fuel TEXT,
    transmission TEXT,
    engine TEXT,
    mileage_km INTEGER,
    city TEXT,
    photo_url TEXT,
    has_vin_badge INTEGER DEFAULT 0,
    description TEXT,
    phone TEXT,
    vin_masked TEXT,
    parameters_json TEXT,
    photo_urls_json TEXT,
    detail_scraped INTEGER DEFAULT 0,
    detail_error TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    archived_at TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    last_run_id INTEGER,
    updated_at TEXT,
    FOREIGN KEY(last_run_id) REFERENCES scrape_runs(id)
);

CREATE TABLE IF NOT EXISTS run_listings (
    run_id INTEGER NOT NULL,
    autoplius_id INTEGER NOT NULL,
    price_eur INTEGER,
    title TEXT,
    detail_scraped INTEGER DEFAULT 0,
    PRIMARY KEY (run_id, autoplius_id),
    FOREIGN KEY(run_id) REFERENCES scrape_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_eur);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON scrape_runs(finished_at);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db_path(data_dir: Path) -> Path:
    return Path(data_dir) / "autoplius.db"


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "description_ru" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN description_ru TEXT")
    if "status" not in cols:
        conn.execute(
            "ALTER TABLE listings ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )
    if "archived_at" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN archived_at TEXT")
    if "price_net_eur" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN price_net_eur INTEGER")
    if "price_gross_eur" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN price_gross_eur INTEGER")
    if "price_vat_note" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN price_vat_note TEXT")
    if "manual_overrides_json" not in cols:
        conn.execute("ALTER TABLE listings ADD COLUMN manual_overrides_json TEXT")

    cols = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    if "status" in cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status)"
        )

    run_cols = {row[1] for row in conn.execute("PRAGMA table_info(scrape_runs)")}
    for name, ddl in (
        ("scrape_mode", "TEXT"),
        ("new_listings_found", "INTEGER"),
        ("enrich_new_only", "INTEGER DEFAULT 0"),
        ("photos_uploaded", "INTEGER"),
    ):
        if name not in run_cols:
            conn.execute(f"ALTER TABLE scrape_runs ADD COLUMN {name} {ddl}")


def _is_minio_photo_url(url: str | None) -> bool:
    return bool(url and url.startswith("/media/object"))


def _is_external_photo_url(url: str | None) -> bool:
    return bool(url and url.startswith("http"))


def _preserve_stored_photos(row: dict[str, Any], existing: sqlite3.Row) -> None:
    """Keep MinIO URLs when scrape refreshed only external autoplius links."""
    if not _should_keep_stored_photos(existing["photo_url"], row.get("photo_url")):
        return
    if row.get("detail_scraped"):
        try:
            new_urls = json.loads(row.get("photo_urls_json") or "[]")
            old_urls = json.loads(existing["photo_urls_json"] or "[]")
        except json.JSONDecodeError:
            new_urls, old_urls = [], []
        new_external = [url for url in new_urls if _is_external_photo_url(url)]
        if len(new_external) > len(old_urls):
            return
    row["photo_url"] = existing["photo_url"]
    row["photo_urls_json"] = existing["photo_urls_json"]


def _should_keep_stored_photos(existing_url: str | None, new_url: str | None) -> bool:
    return _is_minio_photo_url(existing_url) and _is_external_photo_url(new_url)


def _listing_row(item: dict[str, Any], *, run_id: int | None, seen_at: str) -> dict[str, Any]:
    return {
        "autoplius_id": int(item["autoplius_id"]),
        "url": item.get("url"),
        "title": item.get("title"),
        "year": item.get("year"),
        "body_type": item.get("body_type"),
        "price_eur": item.get("price_eur"),
        "price_net_eur": item.get("price_net_eur"),
        "price_gross_eur": item.get("price_gross_eur"),
        "price_vat_note": item.get("price_vat_note"),
        "fuel": item.get("fuel"),
        "transmission": item.get("transmission"),
        "engine": item.get("engine"),
        "mileage_km": item.get("mileage_km"),
        "city": item.get("city"),
        "photo_url": item.get("photo_url"),
        "has_vin_badge": 1 if item.get("has_vin_badge") else 0,
        "description": item.get("description"),
        "description_ru": item.get("description_ru"),
        "phone": item.get("phone"),
        "vin_masked": item.get("vin_masked"),
        "parameters_json": json.dumps(item.get("parameters") or {}, ensure_ascii=False),
        "photo_urls_json": json.dumps(item.get("photo_urls") or [], ensure_ascii=False),
        "detail_scraped": 1 if item.get("detail_scraped") else 0,
        "detail_error": item.get("detail_error"),
        "status": item.get("status") or LISTING_STATUS_ACTIVE,
        "archived_at": item.get("archived_at"),
        "last_run_id": run_id,
        "seen_at": seen_at,
        "updated_at": _utc_now(),
    }


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _archive_listings(
    conn: sqlite3.Connection,
    autoplius_ids: list[int],
    *,
    archived_at: str,
) -> int:
    if not autoplius_ids:
        return 0
    placeholders = ",".join("?" for _ in autoplius_ids)
    cur = conn.execute(
        f"""
        UPDATE listings
        SET status = ?, archived_at = ?, updated_at = ?
        WHERE autoplius_id IN ({placeholders})
          AND COALESCE(status, 'active') = 'active'
        """,
        [LISTING_STATUS_ARCHIVED, archived_at, _utc_now(), *autoplius_ids],
    )
    return int(cur.rowcount)


def _upsert_listing(conn: sqlite3.Connection, row: dict[str, Any], *, seen_at: str) -> None:
    existing = conn.execute(
        "SELECT * FROM listings WHERE autoplius_id = ?",
        (row["autoplius_id"],),
    ).fetchone()

    if existing is not None:
        _preserve_stored_photos(row, existing)
        keep_detail = int(existing["detail_scraped"] or 0) and not row["detail_scraped"]
        merged = merge_listing_row(_row_dict(existing), row, keep_detail=keep_detail)
        merged["last_seen_at"] = seen_at
        merged["updated_at"] = _utc_now()
        conn.execute(
            """
            UPDATE listings SET
                url = :url,
                title = :title,
                year = :year,
                body_type = :body_type,
                price_eur = :price_eur,
                price_net_eur = :price_net_eur,
                price_gross_eur = :price_gross_eur,
                price_vat_note = :price_vat_note,
                fuel = :fuel,
                transmission = :transmission,
                engine = :engine,
                mileage_km = :mileage_km,
                city = :city,
                photo_url = :photo_url,
                has_vin_badge = :has_vin_badge,
                description = :description,
                description_ru = :description_ru,
                phone = :phone,
                vin_masked = :vin_masked,
                parameters_json = :parameters_json,
                photo_urls_json = :photo_urls_json,
                detail_scraped = :detail_scraped,
                detail_error = :detail_error,
                status = :status,
                archived_at = :archived_at,
                manual_overrides_json = :manual_overrides_json,
                last_seen_at = :last_seen_at,
                last_run_id = :last_run_id,
                updated_at = :updated_at
            WHERE autoplius_id = :autoplius_id
            """,
            merged,
        )
        return

    row = {
        **row,
        "status": LISTING_STATUS_ACTIVE,
        "archived_at": None,
    }
    conn.execute(
        """
        INSERT INTO listings (
            autoplius_id, url, title, year, body_type, price_eur, price_net_eur,
            price_gross_eur, price_vat_note, fuel,
            transmission, engine, mileage_km, city, photo_url, has_vin_badge,
            description, description_ru, phone, vin_masked, parameters_json, photo_urls_json,
            detail_scraped, detail_error, status, archived_at,
            first_seen_at, last_seen_at, last_run_id, updated_at
        ) VALUES (
            :autoplius_id, :url, :title, :year, :body_type, :price_eur, :price_net_eur,
            :price_gross_eur, :price_vat_note, :fuel,
            :transmission, :engine, :mileage_km, :city, :photo_url, :has_vin_badge,
            :description, :description_ru, :phone, :vin_masked, :parameters_json, :photo_urls_json,
            :detail_scraped, :detail_error, :status, :archived_at,
            :seen_at, :seen_at, :last_run_id, :updated_at
        )
        """,
        row,
    )


def upsert_listing_item(
    db_path: Path,
    item: dict[str, Any],
    *,
    seen_at: str | None = None,
) -> None:
    """Upsert one listing row (used for incremental target-scrape checkpoints)."""
    init_db(db_path)
    when = seen_at or _utc_now()
    with connect(db_path) as conn:
        row = _listing_row(item, run_id=None, seen_at=when)
        _upsert_listing(conn, row, seen_at=when)


def save_payload_to_db(
    db_path: Path,
    payload: dict[str, Any],
    *,
    snapshot_path: str | None = None,
) -> tuple[int, int]:
    """Insert scrape run + upsert listings. Returns (run_id, archived_count)."""
    init_db(db_path)
    snap = snapshot_path or ""
    finished_at = payload.get("finished_at") or _utc_now()
    diff = payload.get("diff_vs_previous") or {}

    with connect(db_path) as conn:
        if snap:
            existing = conn.execute(
                "SELECT id FROM scrape_runs WHERE snapshot_path = ?",
                (snap,),
            ).fetchone()
            if existing:
                return int(existing["id"]), 0

        cur = conn.execute(
            """
            INSERT INTO scrape_runs (
                mode, started_at, finished_at, duration_sec, pages_scraped,
                listing_count, details_scraped, details_failed, enrich_details,
                diff_new, diff_removed, diff_unchanged, snapshot_path,
                page_stats_json, scrape_mode, new_listings_found, enrich_new_only,
                photos_uploaded, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("mode") or "test",
                payload.get("started_at"),
                finished_at,
                payload.get("duration_sec"),
                payload.get("pages_scraped"),
                payload.get("listing_count"),
                payload.get("details_scraped"),
                payload.get("details_failed"),
                1 if payload.get("enrich_details") else 0,
                diff.get("new"),
                diff.get("removed"),
                diff.get("unchanged"),
                snap or None,
                json.dumps(payload.get("page_stats") or [], ensure_ascii=False),
                payload.get("scrape_mode"),
                payload.get("new_listings_found"),
                1 if payload.get("enrich_new_only") else 0,
                (payload.get("photo_sync") or {}).get("uploaded"),
                _utc_now(),
            ),
        )
        run_id = int(cur.lastrowid)

        for item in payload.get("listings") or []:
            if item.get("autoplius_id") is None:
                continue
            row = _listing_row(item, run_id=run_id, seen_at=finished_at)
            _upsert_listing(conn, row, seen_at=finished_at)
            conn.execute(
                """
                INSERT OR IGNORE INTO run_listings (run_id, autoplius_id, price_eur, title, detail_scraped)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    row["autoplius_id"],
                    row["price_eur"],
                    row["title"],
                    row["detail_scraped"],
                ),
            )

        archived_count = 0
        if (
            payload.get("scrape_mode") in {"full", "target"}
            and payload.get("archive_removed", True)
        ):
            archived_count = _archive_listings(
                conn,
                payload.get("removed_listing_ids") or [],
                archived_at=finished_at,
            )

        return run_id, archived_count


def import_snapshots(db_path: Path, data_dir: Path) -> dict[str, int]:
    """Import all JSON snapshots (oldest first) plus latest.json if needed."""
    init_db(db_path)
    paths: list[Path] = []
    for mode in ("test", "prod"):
        root = data_dir / mode / "snapshots"
        if root.is_dir():
            paths.extend(sorted(root.rglob("*.json")))

    imported = 0
    skipped = 0
    listings_touch = 0
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        before = _count(db_path, "listings")
        run_id, _archived = save_payload_to_db(db_path, payload, snapshot_path=str(path))
        after = _count(db_path, "listings")
        listings_touch += max(0, after - before)
        # count as imported if run exists
        if run_id:
            imported += 1

    latest = data_dir / "latest.json"
    if latest.is_file():
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            save_payload_to_db(db_path, payload, snapshot_path=str(latest.resolve()))
        except (OSError, json.JSONDecodeError):
            skipped += 1

    return {
        "runs": _count(db_path, "scrape_runs"),
        "listings": _count(db_path, "listings"),
        "run_listings": _count(db_path, "run_listings"),
        "snapshots_processed": imported,
        "snapshots_skipped": skipped,
        "new_listings_approx": listings_touch,
    }


def _count(db_path: Path, table: str) -> int:
    with connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
        return int(row["c"])


def load_known_ids(db_path: Path) -> set[int]:
    if not db_path.is_file():
        return set()
    with connect(db_path) as conn:
        rows = conn.execute("SELECT autoplius_id FROM listings").fetchall()
    return {int(row["autoplius_id"]) for row in rows}


def load_detail_scraped_ids(db_path: Path) -> set[int]:
    if not db_path.is_file():
        return set()
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT autoplius_id FROM listings WHERE detail_scraped = 1"
        ).fetchall()
    return {int(row["autoplius_id"]) for row in rows}


def fetch_listings_pending_detail(db_path: Path) -> list[dict[str, Any]]:
    """Active listings that still need a successful detail scrape."""
    if not db_path.is_file():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM listings
            WHERE COALESCE(detail_scraped, 0) = 0
              AND (status IS NULL OR status = ?)
            ORDER BY autoplius_id ASC
            """,
            (LISTING_STATUS_ACTIVE,),
        ).fetchall()
    return [row_to_listing(row) for row in rows]


def hours_since_last_full_scrape(db_path: Path, *, min_listings: int = 50) -> float | None:
    """Hours since the last run that scraped many pages (full catalog refresh)."""
    if not db_path.is_file():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT finished_at FROM scrape_runs
            WHERE pages_scraped >= 10 AND listing_count >= ?
            ORDER BY id DESC LIMIT 1
            """,
            (min_listings,),
        ).fetchone()
    if not row or not row["finished_at"]:
        return None
    try:
        finished = datetime.fromisoformat(str(row["finished_at"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = datetime.now(timezone.utc) - finished
    return delta.total_seconds() / 3600.0


def row_to_listing(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    listing = {
        "autoplius_id": row["autoplius_id"],
        "url": row["url"],
        "title": row["title"],
        "year": row["year"],
        "body_type": row["body_type"],
        "price_eur": row["price_eur"],
        "price_net_eur": row["price_net_eur"] if "price_net_eur" in keys else None,
        "price_gross_eur": row["price_gross_eur"] if "price_gross_eur" in keys else None,
        "price_vat_note": row["price_vat_note"] if "price_vat_note" in keys else None,
        "fuel": row["fuel"],
        "transmission": row["transmission"],
        "engine": row["engine"],
        "mileage_km": row["mileage_km"],
        "city": row["city"],
        "photo_url": row["photo_url"],
        "has_vin_badge": bool(row["has_vin_badge"]) if "has_vin_badge" in keys else False,
        "description": row["description"] if "description" in keys else None,
        "description_ru": row["description_ru"] if "description_ru" in keys else None,
        "phone": row["phone"] if "phone" in keys else None,
        "vin_masked": row["vin_masked"] if "vin_masked" in keys else None,
        "parameters": json.loads(row["parameters_json"] or "{}") if "parameters_json" in keys else {},
        "photo_urls": normalize_photo_list(json.loads(row["photo_urls_json"] or "[]"))
        if "photo_urls_json" in keys
        else [],
        "detail_scraped": bool(row["detail_scraped"]) if "detail_scraped" in keys else False,
        "detail_error": row["detail_error"] if "detail_error" in keys else None,
        "status": row["status"] if "status" in keys else LISTING_STATUS_ACTIVE,
        "archived_at": row["archived_at"] if "archived_at" in keys else None,
        "first_seen_at": row["first_seen_at"] if "first_seen_at" in keys else None,
        "last_seen_at": row["last_seen_at"] if "last_seen_at" in keys else None,
        "last_run_id": row["last_run_id"] if "last_run_id" in keys else None,
        "updated_at": row["updated_at"] if "updated_at" in keys else None,
        "manual_overrides": parse_manual_overrides(
            row["manual_overrides_json"] if "manual_overrides_json" in keys else None
        ),
    }
    listing = localize_listing(listing)
    photos = listing.get("photo_urls") or []
    listing["photo_urls"] = photos
    if photos:
        listing["photo_url"] = photos[0]
    return listing


def fetch_listings(
    db_path: Path,
    *,
    q: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "price_asc",
    details_only: bool = False,
    engine_upto_liters: float | None = None,
    engine_volume_missing: bool = False,
    passable_only: bool = False,
    listing_status: str = "active",
    older_than_3_only: bool = False,
    lite: bool = False,
    catalog_filter: bool = True,
) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []

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

    order_sql = {
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
    }.get(sort, "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur ASC")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = "*" if not lite else (
        "autoplius_id, url, title, year, body_type, price_eur, price_net_eur, "
        "price_gross_eur, price_vat_note, fuel, transmission, engine, mileage_km, "
        "city, photo_url, photo_urls_json, has_vin_badge, parameters_json, "
        "first_seen_at, last_seen_at, status, archived_at, detail_scraped"
    )
    sql = f"SELECT {columns} FROM listings {where} ORDER BY {order_sql}"

    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        listings = [row_to_listing(r) for r in rows]

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


def fetch_listing(db_path: Path, listing_id: int) -> dict[str, Any] | None:
    if not db_path.is_file():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM listings WHERE autoplius_id = ?",
            (listing_id,),
        ).fetchone()
        return row_to_listing(row) if row else None


def fetch_all_listings(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM listings ORDER BY autoplius_id ASC").fetchall()
        return [row_to_listing(r) for r in rows]


def update_listing_photos(
    db_path: Path,
    listing_id: int,
    *,
    photo_url: str | None,
    photo_urls: list[str],
) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE listings SET
                photo_url = ?,
                photo_urls_json = ?,
                updated_at = ?
            WHERE autoplius_id = ?
            """,
            (
                photo_url,
                json.dumps(photo_urls, ensure_ascii=False),
                _utc_now(),
                listing_id,
            ),
        )


def update_listing_detail(db_path: Path, listing_id: int, detail: dict[str, Any]) -> None:
    """Apply a fresh detail scrape (external photo URLs, not MinIO)."""
    photo_urls = normalize_photo_list(detail.get("photo_urls") or [])
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE listings SET
                url = COALESCE(?, url),
                title = COALESCE(?, title),
                price_eur = COALESCE(?, price_eur),
                price_net_eur = COALESCE(?, price_net_eur),
                price_gross_eur = COALESCE(?, price_gross_eur),
                price_vat_note = COALESCE(?, price_vat_note),
                description = COALESCE(?, description),
                phone = COALESCE(?, phone),
                vin_masked = COALESCE(?, vin_masked),
                parameters_json = COALESCE(?, parameters_json),
                photo_url = ?,
                photo_urls_json = ?,
                detail_scraped = 1,
                detail_error = NULL,
                updated_at = ?
            WHERE autoplius_id = ?
            """,
            (
                detail.get("url"),
                detail.get("title"),
                detail.get("price_eur"),
                detail.get("price_net_eur"),
                detail.get("price_gross_eur"),
                detail.get("price_vat_note"),
                detail.get("description"),
                detail.get("phone"),
                detail.get("vin_masked"),
                json.dumps(detail.get("parameters") or {}, ensure_ascii=False)
                if detail.get("parameters")
                else None,
                photo_urls[0] if photo_urls else None,
                json.dumps(photo_urls, ensure_ascii=False),
                _utc_now(),
                listing_id,
            ),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return int(text)
    return int(value)


def _normalize_admin_patch(patch: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in ADMIN_EDITABLE_FIELDS:
            continue
        if key in {"price_eur", "price_net_eur", "price_gross_eur", "mileage_km"}:
            normalized[key] = _optional_int(value)
        elif key in {"has_vin_badge", "detail_scraped"}:
            normalized[key] = 1 if value in {True, 1, "1", "on", "true", "yes"} else 0
        elif key == "status":
            status = str(value or LISTING_STATUS_ACTIVE).strip().lower()
            normalized[key] = (
                LISTING_STATUS_ARCHIVED if status == LISTING_STATUS_ARCHIVED else LISTING_STATUS_ACTIVE
            )
        elif key == "archived_at":
            text = str(value or "").strip()
            normalized[key] = text or None
        elif key == "photo_urls_json":
            if isinstance(value, list):
                urls = normalize_photo_list(value)
            else:
                urls = normalize_photo_list(
                    [line.strip() for line in str(value or "").splitlines() if line.strip()]
                )
            normalized[key] = json.dumps(urls, ensure_ascii=False)
            normalized["photo_url"] = urls[0] if urls else None
        elif key == "parameters_json":
            if isinstance(value, dict):
                normalized[key] = json.dumps(value, ensure_ascii=False)
            else:
                text = str(value or "").strip()
                if not text:
                    normalized[key] = json.dumps({}, ensure_ascii=False)
                else:
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise ValueError("parameters_json must be valid JSON") from exc
                    if not isinstance(parsed, dict):
                        raise ValueError("parameters_json must be a JSON object")
                    normalized[key] = json.dumps(parsed, ensure_ascii=False)
        elif isinstance(value, str):
            text = value.strip()
            normalized[key] = text or None
        else:
            normalized[key] = value
    return normalized


def update_listing_admin(
    db_path: Path,
    listing_id: int,
    patch: dict[str, Any],
    *,
    clear_overrides: bool = False,
) -> dict[str, Any] | None:
    """Apply manual admin edits and lock touched fields from scraper overwrite."""
    init_db(db_path)
    normalized = _normalize_admin_patch(patch)
    if not normalized and not clear_overrides:
        return fetch_listing(db_path, listing_id)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT manual_overrides_json FROM listings WHERE autoplius_id = ?",
            (listing_id,),
        ).fetchone()
        if existing is None:
            return None

        locked = set() if clear_overrides else parse_manual_overrides(existing["manual_overrides_json"])
        locked.update(key for key in normalized if key in ADMIN_EDITABLE_FIELDS)
        normalized["manual_overrides_json"] = encode_manual_overrides(locked)

        if normalized.get("status") == LISTING_STATUS_ARCHIVED and not normalized.get("archived_at"):
            normalized["archived_at"] = _utc_now()
        if normalized.get("status") == LISTING_STATUS_ACTIVE:
            normalized["archived_at"] = None

        assignments = []
        params: dict[str, Any] = {"autoplius_id": listing_id, "updated_at": _utc_now()}
        for key, value in normalized.items():
            assignments.append(f"{key} = :{key}")
            params[key] = value
        assignments.append("updated_at = :updated_at")
        conn.execute(
            f"UPDATE listings SET {', '.join(assignments)} WHERE autoplius_id = :autoplius_id",
            params,
        )
    return fetch_listing(db_path, listing_id)


def db_stats(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {"exists": False}
    with connect(db_path) as conn:
        listings = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
        active = conn.execute(
            """
            SELECT COUNT(*) AS c FROM listings
            WHERE status IS NULL OR status = 'active'
            """
        ).fetchone()["c"]
        archived = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE status = 'archived'"
        ).fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) AS c FROM scrape_runs").fetchone()["c"]
        enriched = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE detail_scraped = 1"
        ).fetchone()["c"]
        phones = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE phone IS NOT NULL AND phone != ''"
        ).fetchone()["c"]
        vins = conn.execute(
            "SELECT COUNT(*) AS c FROM listings WHERE vin_masked IS NOT NULL AND vin_masked != ''"
        ).fetchone()["c"]
        last = conn.execute(
            """
            SELECT finished_at, listing_count, details_scraped, scrape_mode,
                   new_listings_found, duration_sec
            FROM scrape_runs ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    return {
        "exists": True,
        "path": str(db_path),
        "listings": listings,
        "active_listings": active,
        "archived_listings": archived,
        "runs": runs,
        "enriched": enriched,
        "with_phone": phones,
        "with_vin": vins,
        "last_run": dict(last) if last else None,
    }


def _row_to_scrape_run(row: sqlite3.Row) -> dict[str, Any]:
    page_stats: list[dict[str, Any]] = []
    raw_stats = row["page_stats_json"]
    if raw_stats:
        try:
            page_stats = json.loads(raw_stats)
        except json.JSONDecodeError:
            page_stats = []

    scrape_mode = row["scrape_mode"]
    if not scrape_mode:
        pages = row["pages_scraped"] or 0
        count = row["listing_count"] or 0
        if pages >= 10 and count >= 50:
            scrape_mode = "full"
        elif pages <= 2 and count <= 25:
            scrape_mode = "smoke"
        else:
            scrape_mode = "partial"

    return {
        "id": row["id"],
        "mode": row["mode"],
        "scrape_mode": scrape_mode,
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "duration_sec": row["duration_sec"],
        "pages_scraped": row["pages_scraped"],
        "listing_count": row["listing_count"],
        "details_scraped": row["details_scraped"],
        "details_failed": row["details_failed"],
        "enrich_details": bool(row["enrich_details"]),
        "enrich_new_only": bool(row["enrich_new_only"]),
        "diff_new": row["diff_new"],
        "diff_removed": row["diff_removed"],
        "diff_unchanged": row["diff_unchanged"],
        "new_listings_found": row["new_listings_found"],
        "photos_uploaded": row["photos_uploaded"],
        "snapshot_path": row["snapshot_path"],
        "page_stats": page_stats,
    }


def count_scrape_runs(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    init_db(db_path)
    with connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0])


def fetch_scrape_runs(
    db_path: Path,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, mode, started_at, finished_at, duration_sec, pages_scraped,
                   listing_count, details_scraped, details_failed, enrich_details,
                   diff_new, diff_removed, diff_unchanged, snapshot_path,
                   page_stats_json, scrape_mode, new_listings_found, enrich_new_only,
                   photos_uploaded
            FROM scrape_runs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [_row_to_scrape_run(row) for row in rows]


def scrape_runs_analytics(db_path: Path, *, recent_limit: int = 24) -> dict[str, Any]:
    """Aggregate metrics for the analytics dashboard."""
    if not db_path.is_file():
        return {"exists": False}

    init_db(db_path)
    with connect(db_path) as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS runs,
                ROUND(AVG(duration_sec), 1) AS avg_duration_sec,
                SUM(listing_count) AS total_listings_scraped,
                SUM(details_scraped) AS total_details_scraped,
                SUM(COALESCE(new_listings_found, diff_new, 0)) AS total_new_signal,
                SUM(COALESCE(photos_uploaded, 0)) AS total_photos_uploaded
            FROM scrape_runs
            """
        ).fetchone()

        recent = conn.execute(
            """
            SELECT
                COUNT(*) AS runs,
                ROUND(AVG(duration_sec), 1) AS avg_duration_sec,
                SUM(COALESCE(new_listings_found, diff_new, 0)) AS new_signal
            FROM (
                SELECT duration_sec, new_listings_found, diff_new
                FROM scrape_runs
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (recent_limit,),
        ).fetchone()

        by_mode = conn.execute(
            """
            SELECT
                COALESCE(scrape_mode, 'unknown') AS scrape_mode,
                COUNT(*) AS runs,
                ROUND(AVG(duration_sec), 1) AS avg_duration_sec,
                SUM(COALESCE(new_listings_found, diff_new, 0)) AS new_signal
            FROM scrape_runs
            GROUP BY scrape_mode
            ORDER BY runs DESC
            """
        ).fetchall()

    return {
        "exists": True,
        "totals": dict(totals),
        "recent": dict(recent),
        "recent_limit": recent_limit,
        "by_mode": [dict(row) for row in by_mode],
    }
