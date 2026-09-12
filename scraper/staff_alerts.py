"""Staff alert matching: saved ListingFilters vs newly scraped listings."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlsplit

from scraper.db import (
    STAFF_ALERT_ROLES,
    connect,
    get_user_by_id,
    insert_staff_alert_matches,
    list_staff_alert_rules,
)
from scraper.listing_sql_filters import ListingFilters, build_listing_where

logger = logging.getLogger(__name__)

_FILTER_FIELD_NAMES = {f.name for f in fields(ListingFilters)}


def listing_filters_to_json(filters: ListingFilters) -> str:
    return json.dumps(asdict(filters), ensure_ascii=False, sort_keys=True)


def listing_filters_from_json(raw: str | dict[str, Any]) -> ListingFilters:
    data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    if not isinstance(data, dict):
        raise ValueError("filters payload must be an object")
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key not in _FILTER_FIELD_NAMES:
            continue
        cleaned[key] = value
    for key in ("cities", "body_types", "fuels", "transmissions"):
        if key in cleaned and cleaned[key] is None:
            cleaned[key] = []
        if key in cleaned and not isinstance(cleaned[key], list):
            cleaned[key] = [str(cleaned[key])]
    if "vehicle_rows" in cleaned:
        rows = cleaned["vehicle_rows"] or []
        if not isinstance(rows, list):
            rows = []
        normalized_rows: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_rows.append(
                {
                    "make": str(row.get("make") or "").strip(),
                    "model": str(row.get("model") or "").strip(),
                }
            )
        cleaned["vehicle_rows"] = normalized_rows
    return ListingFilters(**cleaned)


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return (values[0] or "").strip()


def _as_int(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _as_float(raw: str) -> float | None:
    text = (raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _flag_enabled(values: list[str] | None, *, default: bool) -> bool:
    if not values:
        return default
    return "1" in values


def parse_alert_query_string(raw: str) -> tuple[ListingFilters, str]:
    """Parse catalog query/URL into ListingFilters + normalized query string."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty query")
    if "://" in text or text.startswith("/"):
        parts = urlsplit(text)
        query = parts.query
    elif text.startswith("?"):
        query = text[1:]
    else:
        query = text
    query = query.lstrip("?")
    params = parse_qs(query, keep_blank_values=False)

    makes = [unquote_plus(v).strip() for v in params.get("make", []) if (v or "").strip()]
    models = [unquote_plus(v).strip() for v in params.get("model", []) if (v or "").strip()]
    vehicle_rows: list[dict[str, str]] = []
    if makes or models:
        count = max(len(makes), len(models), 1)
        for idx in range(count):
            vehicle_rows.append(
                {
                    "make": makes[idx] if idx < len(makes) else (makes[-1] if makes else ""),
                    "model": models[idx] if idx < len(models) else (models[-1] if models else ""),
                }
            )

    upto_19l = "1" in params.get("upto_19l", [])
    over_3y = "1" in params.get("over_3y", [])
    passable = "1" in params.get("passable", [])
    tab = _first(params.get("tab")) or "all"
    # Alert defaults are permissive: optional catalog flags apply only when present in query.
    filters = ListingFilters(
        q=unquote_plus(_first(params.get("q"))),
        min_price=_as_int(_first(params.get("min_price"))),
        max_price=_as_int(_first(params.get("max_price"))),
        sort=_first(params.get("sort")) or "added_desc",
        listing_status="archived" if tab == "archived" else "active",
        older_than_3_only=over_3y,
        passable_only=passable,
        engine_volume_missing=tab == "no_volume",
        electric_only=tab == "electric",
        exclude_electric=tab == "all" and "tab" in params,
        engine_upto_liters=1.9 if upto_19l else None,
        # Match raw scrape inserts; do not require catalog-year completeness.
        catalog_filter=False,
        exclude_blocked_makes=True,
        volume_from=_as_float(_first(params.get("volume_from"))),
        volume_to=_as_float(_first(params.get("volume_to"))),
        cities=[unquote_plus(v).strip() for v in params.get("city", []) if (v or "").strip()],
        body_types=[unquote_plus(v).strip() for v in params.get("body_type", []) if (v or "").strip()],
        fuels=[unquote_plus(v).strip() for v in params.get("fuel", []) if (v or "").strip()],
        transmissions=[
            unquote_plus(v).strip() for v in params.get("transmission", []) if (v or "").strip()
        ],
        vehicle_rows=vehicle_rows,
        year_from=_as_int(_first(params.get("year_from"))),
        year_to=_as_int(_first(params.get("year_to"))),
    )
    return filters, query


def filter_candidate_ids(
    db_path: Path,
    filters: ListingFilters,
    candidate_ids: list[int],
) -> list[int]:
    if not candidate_ids:
        return []
    if not db_path.is_file():
        return []
    unique_ids = sorted({int(x) for x in candidate_ids})
    clauses, params = build_listing_where(filters)
    placeholders = ",".join("?" for _ in unique_ids)
    clauses.append(f"autoplius_id IN ({placeholders})")
    params.extend(unique_ids)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT autoplius_id FROM listings {where}"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [int(row[0]) for row in rows]


def process_staff_alerts_for_new_listings(
    db_path: Path,
    new_listing_ids: list[int],
) -> int:
    """Match newly inserted listings against enabled staff alert rules.

    Returns number of newly inserted match rows.
    """
    candidates = sorted({int(x) for x in new_listing_ids if int(x) > 0})
    if not candidates:
        return 0

    rules = list_staff_alert_rules(db_path, enabled_only=True)
    if not rules:
        return 0

    to_insert: list[tuple[int, int, int]] = []
    for rule in rules:
        user = get_user_by_id(db_path, int(rule["user_id"]))
        if user is None or user.get("role") not in STAFF_ALERT_ROLES:
            continue
        try:
            filters = listing_filters_from_json(rule["filters_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("skip alert rule %s: invalid filters_json", rule.get("id"))
            continue
        matched_ids = filter_candidate_ids(db_path, filters, candidates)
        for autoplius_id in matched_ids:
            to_insert.append((int(rule["id"]), int(rule["user_id"]), int(autoplius_id)))

    if not to_insert:
        return 0
    created = insert_staff_alert_matches(db_path, to_insert)
    if created:
        logger.info(
            "staff alerts: %s new match row(s) from %s candidate listing(s)",
            created,
            len(candidates),
        )
    return created
