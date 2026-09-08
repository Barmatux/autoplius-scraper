"""Build auto160 catalog match candidates from local engine_catalog and persist links."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from scraper.auto160_catalog_client import (
    Auto160CatalogClient,
    Auto160CatalogError,
    CatalogCandidate,
    MatchResult,
    reconcile_after_parse,
)
from scraper.db import fetch_engine_catalog, init_db, set_engine_catalog_auto160_item_id

logger = logging.getLogger(__name__)


def auto160_catalog_configured() -> bool:
    return bool(
        (os.environ.get("AUTO160_CATALOG_BASE_URL") or "").strip()
        and (os.environ.get("AUTO160_CATALOG_API_KEY") or "").strip()
    )


def _cm3_to_liters(cm3: int | None) -> float | None:
    if cm3 is None:
        return None
    try:
        value = int(cm3)
    except (TypeError, ValueError):
        return None
    if value < 100 or value > 20000:
        return None
    return round(value / 1000.0, 3)


def candidates_from_engine_catalog(db_path: Path) -> list[CatalogCandidate]:
    entries = fetch_engine_catalog(db_path)
    out: list[CatalogCandidate] = []
    for entry in entries:
        make = (entry.get("make") or "").strip()
        model = (entry.get("model") or "").strip()
        if not make or not model:
            continue
        cm3 = entry.get("customs_cm3")
        if cm3 is None:
            cm3 = entry.get("suggested_cm3")
        fuel = (entry.get("fuel") or "").strip() or None
        engine_label = (entry.get("engine_label") or "").strip() or None
        out.append(
            CatalogCandidate(
                external_ref=str(entry["id"]),
                make=make,
                model=model,
                fuel_type=fuel,
                engine_volume_l=_cm3_to_liters(cm3 if isinstance(cm3, int) else None),
                source_external_id=engine_label,
            )
        )
    return out


def reconcile_engine_catalog_with_auto160(db_path: Path) -> dict[str, Any]:
    """Separate step after parse/catalog refresh. Skips when env is not configured."""
    if not auto160_catalog_configured():
        return {"skipped": True, "reason": "auto160 catalog env not set"}

    init_db(db_path)
    candidates = candidates_from_engine_catalog(db_path)
    if not candidates:
        return {"skipped": False, "candidates": 0, "matched": 0, "not_found": 0}

    matched = 0
    not_found = 0

    def on_matched(result: MatchResult) -> None:
        nonlocal matched
        if not result.external_ref or result.matched_catalog_item_id is None:
            return
        try:
            entry_id = int(result.external_ref)
        except ValueError:
            logger.warning("auto160 match: bad external_ref %r", result.external_ref)
            return
        if set_engine_catalog_auto160_item_id(
            db_path,
            entry_id,
            catalog_item_id=int(result.matched_catalog_item_id),
        ):
            matched += 1

    def on_not_found(result: MatchResult) -> None:
        nonlocal not_found
        not_found += 1
        logger.info(
            "auto160 catalog gap: %s %s ref=%s gap_id=%s",
            result.make,
            result.model,
            result.external_ref,
            result.gap_id,
        )

    try:
        client = Auto160CatalogClient()
        results = reconcile_after_parse(
            candidates,
            on_matched=on_matched,
            on_not_found=on_not_found,
            client=client,
            enqueue_gaps=True,
        )
    except (Auto160CatalogError, ValueError) as exc:
        logger.warning("auto160 catalog reconcile failed: %s", exc)
        return {
            "skipped": False,
            "error": str(exc),
            "candidates": len(candidates),
            "matched": matched,
            "not_found": not_found,
        }

    return {
        "skipped": False,
        "candidates": len(candidates),
        "results": len(results),
        "matched": matched,
        "not_found": not_found,
    }
