from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from autoplius.listing_display import listing_make_model
from autoplius.engine_volume import _parse_volume_cm3_from_text, engine_volume_cm3
from autoplius.catalog_filters import is_pickup_listing
from autoplius.make_model_filters import is_blocked_make

CATALOG_UPTO_LITERS_DEFAULT = 1.9

_db_path: Path | None = None
_catalog_cache: dict[tuple[str, str, str, str], int] | None = None
_catalog_cache_mtime: float | None = None


def configure_catalog_db(db_path: Path | None) -> None:
    global _db_path
    _db_path = db_path
    invalidate_catalog_cache()


def invalidate_catalog_cache() -> None:
    global _catalog_cache, _catalog_cache_mtime
    _catalog_cache = None
    _catalog_cache_mtime = None


def catalog_engine_label(item: dict[str, Any]) -> str:
    engine = (item.get("engine") or "").strip()
    if engine:
        return engine
    params = item.get("parameters") or {}
    for key in ("Двигатель", "Variklis"):
        value = params.get(key)
        if value:
            return str(value).strip()
    return "—"


def catalog_fuel_label(item: dict[str, Any]) -> str:
    return (item.get("fuel") or "").strip()


def catalog_key_from_item(item: dict[str, Any]) -> tuple[str, str, str, str]:
    make, model = listing_make_model(item)
    return (
        make if make != "—" else "",
        model,
        catalog_engine_label(item),
        catalog_fuel_label(item),
    )


def catalog_entry_liters(entry: dict[str, Any]) -> float | None:
    for key in ("customs_cm3", "suggested_cm3"):
        cm3 = entry.get(key)
        if cm3:
            return int(cm3) / 1000
    cm3 = _parse_volume_cm3_from_text(entry.get("engine_label") or "")
    if cm3 is not None:
        return cm3 / 1000
    return None


def filter_catalog_entries_upto_liters(
    entries: list[dict[str, Any]],
    *,
    enabled: bool,
    max_liters: float = CATALOG_UPTO_LITERS_DEFAULT,
) -> list[dict[str, Any]]:
    if not enabled:
        return entries
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        liters = catalog_entry_liters(entry)
        if liters is not None and liters <= max_liters:
            filtered.append(entry)
    return filtered


def aggregate_catalog_groups(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for item in listings:
        if is_pickup_listing(item):
            continue
        make, model, engine_label, fuel = catalog_key_from_item(item)
        if not make or is_blocked_make(make) or not engine_label or engine_label == "—":
            continue
        key = (make, model, engine_label, fuel)
        bucket = grouped.setdefault(
            key,
            {
                "make": make,
                "model": model,
                "engine_label": engine_label,
                "fuel": fuel,
                "listing_count": 0,
                "parsed_cm3_values": Counter(),
            },
        )
        bucket["listing_count"] += 1
        parsed = engine_volume_cm3(item)
        if parsed is not None:
            bucket["parsed_cm3_values"][parsed] += 1

    rows: list[dict[str, Any]] = []
    for bucket in grouped.values():
        parsed_values = bucket.pop("parsed_cm3_values")
        suggested = parsed_values.most_common(1)[0][0] if parsed_values else None
        rows.append(
            {
                **bucket,
                "suggested_cm3": suggested,
            }
        )
    rows.sort(key=lambda row: (row["make"].casefold(), row["model"].casefold(), row["engine_label"].casefold()))
    return rows


def build_catalog_tree(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_make: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entry in entries:
        by_make.setdefault(entry["make"], {}).setdefault(entry["model"], []).append(entry)

    tree: list[dict[str, Any]] = []
    for make in sorted(by_make.keys(), key=str.casefold):
        models: list[dict[str, Any]] = []
        for model in sorted(by_make[make].keys(), key=str.casefold):
            models.append(
                {
                    "model": model,
                    "entries": sorted(
                        by_make[make][model],
                        key=lambda row: (row["engine_label"].casefold(), row["fuel"].casefold()),
                    ),
                }
            )
        tree.append({"make": make, "models": models})
    return tree


def split_catalog_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    new_entries = [entry for entry in entries if entry.get("is_new")]
    main_entries = [entry for entry in entries if not entry.get("is_new")]
    new_entries.sort(
        key=lambda row: (row.get("updated_at") or "", row["make"].casefold(), row["model"].casefold()),
        reverse=True,
    )
    return {
        "new_tree": build_catalog_tree(new_entries),
        "main_tree": build_catalog_tree(main_entries),
        "new_count": len(new_entries),
    }


def catalog_stats(entries: list[dict[str, Any]]) -> dict[str, int]:
    manual = sum(1 for entry in entries if entry.get("is_manual"))
    filled = sum(1 for entry in entries if entry.get("customs_cm3") is not None)
    new_count = sum(1 for entry in entries if entry.get("is_new"))
    return {
        "total": len(entries),
        "manual": manual,
        "filled": filled,
        "missing": len(entries) - filled,
        "new": new_count,
    }


def refresh_engine_catalog(db_path: Path) -> tuple[int, int]:
    from scraper.db import fetch_listings, sync_engine_catalog_from_listings

    listings = fetch_listings(db_path, passable_only=False, listing_status="active")
    groups = aggregate_catalog_groups(listings)
    return sync_engine_catalog_from_listings(db_path, groups)


def _load_catalog_cache() -> dict[tuple[str, str, str, str], int]:
    global _catalog_cache, _catalog_cache_mtime
    if _db_path is None or not _db_path.is_file():
        return {}

    mtime = _db_path.stat().st_mtime
    if _catalog_cache is not None and _catalog_cache_mtime == mtime:
        return _catalog_cache

    from scraper.db import fetch_engine_catalog_lookup

    _catalog_cache = fetch_engine_catalog_lookup(_db_path)
    _catalog_cache_mtime = mtime
    return _catalog_cache


def lookup_catalog_cm3(item: dict[str, Any]) -> int | None:
    make, model, engine_label, fuel = catalog_key_from_item(item)
    if not make or not engine_label or engine_label == "—":
        return None

    cache = _load_catalog_cache()
    for key in (
        (make, model, engine_label, fuel),
        (make, model, engine_label, ""),
    ):
        if key in cache:
            return cache[key]
    return None
