from __future__ import annotations

from pathlib import Path

from scraper.auto160_catalog_client import CatalogCandidate
from scraper.auto160_catalog_reconcile import (
    auto160_catalog_configured,
    candidates_from_engine_catalog,
    reconcile_engine_catalog_with_auto160,
)
from scraper.db import connect, init_db, set_engine_catalog_auto160_item_id


def test_catalog_candidate_payload_omits_none():
    row = CatalogCandidate(
        make="BMW",
        model="3 серия",
        external_ref="12",
        year=2015,
        engine_power_hp=136,
    )
    payload = row.to_payload()
    assert payload["make"] == "BMW"
    assert payload["external_ref"] == "12"
    assert "generation" not in payload
    assert "fuel_type" not in payload


def test_candidates_from_engine_catalog(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AUTO160_CATALOG_BASE_URL", raising=False)
    monkeypatch.delenv("AUTO160_CATALOG_API_KEY", raising=False)
    assert not auto160_catalog_configured()

    db = tmp_path / "t.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO engine_catalog (
                make, model, engine_label, fuel, customs_cm3, suggested_cm3,
                listing_count, is_manual, is_new, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, NULL, ?)
            """,
            ("Toyota", "Corolla", "1.6", "Petrol", 1598, None, "2026-01-01T00:00:00+00:00"),
        )

    candidates = candidates_from_engine_catalog(db)
    assert len(candidates) == 1
    assert candidates[0].make == "Toyota"
    assert candidates[0].model == "Corolla"
    assert candidates[0].fuel_type == "Petrol"
    assert candidates[0].engine_volume_l == 1.598
    assert candidates[0].external_ref == "1"

    skipped = reconcile_engine_catalog_with_auto160(db)
    assert skipped["skipped"] is True

    assert set_engine_catalog_auto160_item_id(db, 1, catalog_item_id=42)
    with connect(db) as conn:
        row = conn.execute(
            "SELECT auto160_catalog_item_id FROM engine_catalog WHERE id = 1"
        ).fetchone()
    assert int(row[0]) == 42
