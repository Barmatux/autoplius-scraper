from __future__ import annotations

from typing import Any

LISTING_STATUS_ACTIVE = "active"
LISTING_STATUS_ARCHIVED = "archived"

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
    }
)

MERGE_FIELDS = (
    "url",
    "title",
    "year",
    "body_type",
    "price_eur",
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
)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def merge_listing_row(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    keep_detail: bool,
) -> dict[str, Any]:
    """Field-level merge for an existing listing (av.by-style, not full replace)."""
    merged = dict(incoming)
    merged["status"] = LISTING_STATUS_ACTIVE
    merged["archived_at"] = None

    for field in MERGE_FIELDS:
        if field in PRESERVE_ON_UPDATE_FIELDS:
            if _has_value(existing.get(field)):
                merged[field] = existing[field]
            continue

        if keep_detail and field in DETAIL_FIELDS:
            merged[field] = existing.get(field)
            continue

        new_value = incoming.get(field)
        old_value = existing.get(field)
        if field in {"description_ru", "phone", "vin_masked"} and _has_value(old_value):
            if not _has_value(new_value):
                merged[field] = old_value

    if keep_detail:
        merged["detail_scraped"] = existing.get("detail_scraped")
        merged["detail_error"] = existing.get("detail_error")

    return merged
