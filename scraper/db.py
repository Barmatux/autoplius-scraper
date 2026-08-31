from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


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


def _listing_row(item: dict[str, Any], *, run_id: int | None, seen_at: str) -> dict[str, Any]:
    return {
        "autoplius_id": int(item["autoplius_id"]),
        "url": item.get("url"),
        "title": item.get("title"),
        "year": item.get("year"),
        "body_type": item.get("body_type"),
        "price_eur": item.get("price_eur"),
        "fuel": item.get("fuel"),
        "transmission": item.get("transmission"),
        "engine": item.get("engine"),
        "mileage_km": item.get("mileage_km"),
        "city": item.get("city"),
        "photo_url": item.get("photo_url"),
        "has_vin_badge": 1 if item.get("has_vin_badge") else 0,
        "description": item.get("description"),
        "phone": item.get("phone"),
        "vin_masked": item.get("vin_masked"),
        "parameters_json": json.dumps(item.get("parameters") or {}, ensure_ascii=False),
        "photo_urls_json": json.dumps(item.get("photo_urls") or [], ensure_ascii=False),
        "detail_scraped": 1 if item.get("detail_scraped") else 0,
        "detail_error": item.get("detail_error"),
        "last_run_id": run_id,
        "seen_at": seen_at,
        "updated_at": _utc_now(),
    }


def save_payload_to_db(
    db_path: Path,
    payload: dict[str, Any],
    *,
    snapshot_path: str | None = None,
) -> int:
    """Insert scrape run + upsert listings. Returns run_id (existing or new)."""
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
                return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO scrape_runs (
                mode, started_at, finished_at, duration_sec, pages_scraped,
                listing_count, details_scraped, details_failed, enrich_details,
                diff_new, diff_removed, diff_unchanged, snapshot_path,
                page_stats_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                _utc_now(),
            ),
        )
        run_id = int(cur.lastrowid)

        for item in payload.get("listings") or []:
            if item.get("autoplius_id") is None:
                continue
            row = _listing_row(item, run_id=run_id, seen_at=finished_at)
            existing = conn.execute(
                "SELECT autoplius_id, detail_scraped, first_seen_at FROM listings WHERE autoplius_id = ?",
                (row["autoplius_id"],),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO listings (
                        autoplius_id, url, title, year, body_type, price_eur, fuel,
                        transmission, engine, mileage_km, city, photo_url, has_vin_badge,
                        description, phone, vin_masked, parameters_json, photo_urls_json,
                        detail_scraped, detail_error, first_seen_at, last_seen_at,
                        last_run_id, updated_at
                    ) VALUES (
                        :autoplius_id, :url, :title, :year, :body_type, :price_eur, :fuel,
                        :transmission, :engine, :mileage_km, :city, :photo_url, :has_vin_badge,
                        :description, :phone, :vin_masked, :parameters_json, :photo_urls_json,
                        :detail_scraped, :detail_error, :seen_at, :seen_at,
                        :last_run_id, :updated_at
                    )
                    """,
                    row,
                )
            else:
                # Prefer richer detail data when updating.
                keep_detail = int(existing["detail_scraped"] or 0) and not row["detail_scraped"]
                if keep_detail:
                    conn.execute(
                        """
                        UPDATE listings SET
                            url = COALESCE(:url, url),
                            title = COALESCE(:title, title),
                            year = COALESCE(:year, year),
                            body_type = COALESCE(:body_type, body_type),
                            price_eur = COALESCE(:price_eur, price_eur),
                            fuel = COALESCE(:fuel, fuel),
                            transmission = COALESCE(:transmission, transmission),
                            engine = COALESCE(:engine, engine),
                            mileage_km = COALESCE(:mileage_km, mileage_km),
                            city = COALESCE(:city, city),
                            photo_url = COALESCE(:photo_url, photo_url),
                            last_seen_at = :seen_at,
                            last_run_id = :last_run_id,
                            updated_at = :updated_at
                        WHERE autoplius_id = :autoplius_id
                        """,
                        row,
                    )
                else:
                    conn.execute(
                        """
                        UPDATE listings SET
                            url = :url,
                            title = :title,
                            year = :year,
                            body_type = :body_type,
                            price_eur = :price_eur,
                            fuel = :fuel,
                            transmission = :transmission,
                            engine = :engine,
                            mileage_km = :mileage_km,
                            city = :city,
                            photo_url = :photo_url,
                            has_vin_badge = :has_vin_badge,
                            description = :description,
                            phone = :phone,
                            vin_masked = :vin_masked,
                            parameters_json = :parameters_json,
                            photo_urls_json = :photo_urls_json,
                            detail_scraped = :detail_scraped,
                            detail_error = :detail_error,
                            last_seen_at = :seen_at,
                            last_run_id = :last_run_id,
                            updated_at = :updated_at
                        WHERE autoplius_id = :autoplius_id
                        """,
                        row,
                    )

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

        return run_id


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
        run_id = save_payload_to_db(db_path, payload, snapshot_path=str(path))
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


def row_to_listing(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "autoplius_id": row["autoplius_id"],
        "url": row["url"],
        "title": row["title"],
        "year": row["year"],
        "body_type": row["body_type"],
        "price_eur": row["price_eur"],
        "fuel": row["fuel"],
        "transmission": row["transmission"],
        "engine": row["engine"],
        "mileage_km": row["mileage_km"],
        "city": row["city"],
        "photo_url": row["photo_url"],
        "has_vin_badge": bool(row["has_vin_badge"]),
        "description": row["description"],
        "phone": row["phone"],
        "vin_masked": row["vin_masked"],
        "parameters": json.loads(row["parameters_json"] or "{}"),
        "photo_urls": json.loads(row["photo_urls_json"] or "[]"),
        "detail_scraped": bool(row["detail_scraped"]),
        "detail_error": row["detail_error"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "last_run_id": row["last_run_id"],
    }


def fetch_listings(
    db_path: Path,
    *,
    q: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "price_asc",
    details_only: bool = False,
) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []

    clauses: list[str] = []
    params: list[Any] = []
    if details_only:
        clauses.append("detail_scraped = 1")
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
                OR lower(COALESCE(parameters_json,'')) LIKE ?
                OR CAST(autoplius_id AS TEXT) LIKE ?
            )"""
        )
        params.extend([like] * 8)

    order_sql = {
        "price_asc": "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur ASC",
        "price_desc": "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur DESC",
        "mileage_asc": "CASE WHEN mileage_km IS NULL THEN 1 ELSE 0 END, mileage_km ASC",
        "mileage_desc": "CASE WHEN mileage_km IS NULL THEN 1 ELSE 0 END, mileage_km DESC",
        "year_desc": "CASE WHEN year IS NULL THEN 1 ELSE 0 END, year DESC",
        "title_asc": "CASE WHEN title IS NULL THEN 1 ELSE 0 END, title ASC",
    }.get(sort, "CASE WHEN price_eur IS NULL THEN 1 ELSE 0 END, price_eur ASC")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM listings {where} ORDER BY {order_sql}"

    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_listing(r) for r in rows]


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


def db_stats(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {"exists": False}
    with connect(db_path) as conn:
        listings = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
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
            "SELECT finished_at, listing_count, details_scraped FROM scrape_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "exists": True,
        "path": str(db_path),
        "listings": listings,
        "runs": runs,
        "enriched": enriched,
        "with_phone": phones,
        "with_vin": vins,
        "last_run": dict(last) if last else None,
    }
