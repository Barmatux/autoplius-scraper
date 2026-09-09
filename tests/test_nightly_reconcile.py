from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scraper.db import (
    archive_active_missing_from_search,
    connect,
    fetch_stale_active_listings_for_probe,
    init_db,
)


def _insert_active(db: Path, listing_id: int, *, last_seen: str) -> None:
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO listings (
                autoplius_id, url, title, status, last_seen_at, first_seen_at, updated_at
            ) VALUES (?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                listing_id,
                f"https://ru.autoplius.lt/x-{listing_id}.html",
                f"Car {listing_id}",
                last_seen,
                last_seen,
                last_seen,
            ),
        )


def test_archive_active_missing_respects_safety_gates(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.db"
    init_db(db)
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    _insert_active(db, 1, last_seen=old)
    _insert_active(db, 2, last_seen=old)

    monkeypatch.setenv("NIGHTLY_ARCHIVE_MIN_PAGES", "20")
    monkeypatch.setenv("NIGHTLY_ARCHIVE_MIN_LISTINGS", "500")
    # Too small search — must not archive.
    assert (
        archive_active_missing_from_search(
            db,
            seen_ids={1},
            pages_scraped=5,
            listing_count=100,
            run_started_at=datetime.now(timezone.utc).isoformat(),
        )
        == 0
    )

    monkeypatch.setenv("NIGHTLY_ARCHIVE_MIN_PAGES", "1")
    monkeypatch.setenv("NIGHTLY_ARCHIVE_MIN_LISTINGS", "1")
    archived = archive_active_missing_from_search(
        db,
        seen_ids={1},
        pages_scraped=25,
        listing_count=600,
        run_started_at=datetime.now(timezone.utc).isoformat(),
    )
    assert archived == 1
    with connect(db) as conn:
        statuses = {
            int(r["autoplius_id"]): r["status"]
            for r in conn.execute("SELECT autoplius_id, status FROM listings")
        }
    assert statuses[1] == "active"
    assert statuses[2] == "archived"


def test_fetch_stale_active_for_probe(tmp_path: Path):
    db = tmp_path / "t.db"
    init_db(db)
    fresh = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    _insert_active(db, 10, last_seen=fresh)
    _insert_active(db, 11, last_seen=old)
    rows = fetch_stale_active_listings_for_probe(db, older_than_hours=24, limit=10)
    ids = [int(r["autoplius_id"]) for r in rows]
    assert ids == [11]
