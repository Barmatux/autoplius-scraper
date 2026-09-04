from __future__ import annotations

import json
from typing import Any

from autoplius.listing_titles import is_invalid_listing_title, resolve_listing_title

LISTING_STATUS_ACTIVE = "active"
LISTING_STATUS_ARCHIVED = "archived"

ADMIN_EDITABLE_FIELDS = frozenset(
    {
        "url",
        "title",
        "year",
        "body_type",
        "price_eur",
        "price_net_eur",
        "price_gross_eur",
        "price_vat_note",
        "fuel",
        "transmission",
        "engine",
        "mileage_km",
        "city",
        "photo_url",
        "photo_urls_json",
        "has_vin_badge",
        "description",
        "description_ru",
        "phone",
        "vin_masked",
        "parameters_json",
        "status",
        "archived_at",
        "detail_scraped",
        "detail_error",
    }
)

# Never overwrite these on update (same idea as av.by vin / vin_fetched_at).
PRESERVE_ON_UPDATE_FIELDS = frozenset(
    {
        "first_seen_at",
        "description_ru",
        "phone",
        "vin_masked",
    }
)

# Detail payload: keep existing values when incoming scrape has no detail pass.
DETAIL_FIELDS = frozenset(
    {
        "description",
        "description_ru",
        "phone",
        "vin_masked",
        "parameters_json",
        "photo_urls_json",
        "detail_scraped",
        "detail_error",
        "has_vin_badge",
        "price_net_eur",
        "price_gross_eur",
        "price_vat_note",
        "engine_liters",
    }
)

MERGE_FIELDS = (
    "url",
    "title",
    "year",
    "body_type",
    "price_eur",
    "price_net_eur",
    "price_gross_eur",
    "price_vat_note",
    "fuel",
    "transmission",
    "engine",
    "mileage_km",
    "city",
    "photo_url",
    "has_vin_badge",
    "description",
    "description_ru",
    "phone",
    "vin_masked",
    "parameters_json",
    "photo_urls_json",
    "detail_scraped",
    "detail_error",
    "engine_liters",
)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _photo_urls_json_empty(raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text == "[]":
            return True
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return False
        return not parsed
    if isinstance(raw, list):
        return len(raw) == 0
    return False


def _photo_field_has_data(field: str, value: Any) -> bool:
    if field == "photo_urls_json":
        return not _photo_urls_json_empty(value)
    return _has_value(value)


def parse_manual_overrides(raw: Any) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, (set, frozenset)):
        return {str(item) for item in raw if str(item) in ADMIN_EDITABLE_FIELDS}
    if isinstance(raw, list):
        return {str(item) for item in raw if str(item) in ADMIN_EDITABLE_FIELDS}
    if isinstance(raw, dict):
        return {str(key) for key, enabled in raw.items() if enabled and str(key) in ADMIN_EDITABLE_FIELDS}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        return parse_manual_overrides(parsed)
    return set()


def encode_manual_overrides(fields: set[str]) -> str | None:
    locked = sorted(field for field in fields if field in ADMIN_EDITABLE_FIELDS)
    if not locked:
        return None
    return json.dumps(locked, ensure_ascii=False)


def merge_listing_row(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    keep_detail: bool,
) -> dict[str, Any]:
    """Field-level merge for an existing listing (av.by-style, not full replace)."""
    merged = dict(incoming)
    overrides = parse_manual_overrides(existing.get("manual_overrides_json"))
    merged["manual_overrides_json"] = existing.get("manual_overrides_json")

    if "status" in overrides:
        merged["status"] = existing.get("status") or LISTING_STATUS_ACTIVE
        merged["archived_at"] = existing.get("archived_at")
    else:
        merged["status"] = LISTING_STATUS_ACTIVE
        merged["archived_at"] = None

    for field in MERGE_FIELDS:
        if field in overrides:
            merged[field] = existing.get(field)
            continue

        if field in PRESERVE_ON_UPDATE_FIELDS:
            if _has_value(existing.get(field)):
                merged[field] = existing[field]
            continue

        if keep_detail and field in DETAIL_FIELDS:
            merged[field] = existing.get(field)
            continue

        new_value = incoming.get(field)
        old_value = existing.get(field)
        if field in {"photo_url", "photo_urls_json"}:
            if not _photo_field_has_data(field, new_value) and _photo_field_has_data(field, old_value):
                merged[field] = old_value
                continue
        if field == "title":
            merged[field] = resolve_listing_title(
                title=new_value if _has_value(new_value) else old_value,
                url=incoming.get("url") or existing.get("url"),
                fallback_item={**existing, **incoming, "autoplius_id": incoming.get("autoplius_id") or existing.get("autoplius_id")},
            )
            if is_invalid_listing_title(merged[field]):
                merged[field] = old_value if _has_value(old_value) and not is_invalid_listing_title(old_value) else merged[field]
            continue
        if field in {"description_ru", "phone", "vin_masked"} and _has_value(old_value):
            if not _has_value(new_value):
                merged[field] = old_value

        if field in {
            "price_net_eur",
            "price_gross_eur",
            "price_vat_note",
            "engine_liters",
            "mileage_km",
        }:
            if new_value is None and old_value is not None:
                merged[field] = old_value

    if keep_detail or "detail_scraped" in overrides:
        merged["detail_scraped"] = existing.get("detail_scraped")
    if keep_detail or "detail_error" in overrides:
        merged["detail_error"] = existing.get("detail_error")

    _refresh_merged_engine_liters(merged)
    _refresh_merged_mileage_km(merged)
    return merged


def _merged_parameters(merged: dict[str, Any]) -> dict[str, Any]:
    parameters = merged.get("parameters")
    if isinstance(parameters, dict):
        return parameters
    try:
        parsed = json.loads(merged.get("parameters_json") or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _refresh_merged_engine_liters(merged: dict[str, Any]) -> None:
    """Fill engine_liters from params/engine/description when still missing."""
    from autoplius.engine_volume import engine_volume_liters

    if merged.get("engine_liters") is not None:
        return
    parameters = _merged_parameters(merged)
    liters = engine_volume_liters(
        {
            "title": merged.get("title"),
            "engine": merged.get("engine"),
            "description": merged.get("description"),
            "description_ru": merged.get("description_ru"),
            "parameters": parameters,
        }
    )
    if liters is not None:
        merged["engine_liters"] = liters


def _refresh_merged_mileage_km(merged: dict[str, Any]) -> None:
    """Fill mileage_km from Autoplius parameters when search scrape omitted it."""
    from autoplius.labels import mileage_from_parameters, parse_mileage_km

    if parse_mileage_km(merged.get("mileage_km")) is not None:
        return
    parsed = mileage_from_parameters(_merged_parameters(merged))
    if parsed is not None:
        merged["mileage_km"] = parsed
