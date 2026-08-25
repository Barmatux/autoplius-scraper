from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_latest_ids(data_dir: Path) -> set[int]:
    latest = data_dir / "latest.json"
    if not latest.is_file():
        return set()
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {item["autoplius_id"] for item in payload.get("listings", []) if item.get("autoplius_id")}


def save_snapshot(
    payload: dict[str, Any],
    *,
    data_dir: Path,
    test_mode: bool,
) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir = data_dir / ("test" if test_mode else "prod") / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_now()
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    dated_dir = snapshots_dir / ts.strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = dated_dir / f"{stamp}.json"
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = data_dir / "latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {
        "saved_at": ts.isoformat(),
        "snapshot_path": str(snapshot_path),
        "test_mode": test_mode,
        "listing_count": payload.get("listing_count", 0),
        "pages_scraped": payload.get("pages_scraped", 0),
        "details_scraped": payload.get("details_scraped", 0),
        "details_failed": payload.get("details_failed", 0),
        "enrich_details": payload.get("enrich_details", False),
    }
    meta_path = data_dir / "last_run.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Snapshot saved: %s", snapshot_path)
    return snapshot_path


def diff_stats(current_ids: set[int], previous_ids: set[int]) -> dict[str, int]:
    return {
        "new": len(current_ids - previous_ids),
        "removed": len(previous_ids - current_ids),
        "unchanged": len(current_ids & previous_ids),
    }
