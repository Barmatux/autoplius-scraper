"""Detect pure-electric (non-hybrid) Autoplius listings."""

from __future__ import annotations

from typing import Any

from autoplius.listing_display import listing_make_model

ELECTRIC_MARKERS = (
    "электр",
    "elektr",
    "elektra",
    "electric",
)
HYBRID_OR_ICE_MARKERS = (
    "/",
    "гибрид",
    "hybrid",
    "plug-in",
    "plugin",
    "бенз",
    "benzin",
    "byenzin",
    "дизел",
    "dizel",
    "dyzel",
    "diesel",
    "petrol",
    "gasoline",
    "газ",
)

# Always treat these make/model pairs as battery-electric (even if fuel is missing/odd).
ELECTRIC_MAKE_MODELS = frozenset({("BMW", "i3")})


def _model_matches_electric(model: str, blocked_model: str) -> bool:
    folded = model.strip().casefold()
    target = blocked_model.strip().casefold()
    if not folded or not target:
        return False
    if "," in folded:
        folded = folded.split(",", 1)[0].strip()
    if folded == target:
        return True
    if folded.startswith(f"{target} "):
        return True
    # BMW i3s / i3S
    if target == "i3" and folded.startswith("i3s"):
        return True
    return False


def is_electric_make_model(make: str | None, model: str | None) -> bool:
    make_text = (make or "").strip()
    model_text = (model or "").strip()
    if not make_text or make_text == "—" or not model_text:
        return False
    make_folded = make_text.casefold()
    for electric_make, electric_model in ELECTRIC_MAKE_MODELS:
        if make_folded != electric_make.casefold():
            continue
        if _model_matches_electric(model_text, electric_model):
            return True
    return False


def is_pure_electric_fuel(fuel: str | None) -> bool:
    """True for battery-only cars; false for hybrids and ICE."""
    text = (fuel or "").casefold().strip()
    if not text:
        return False
    if not any(marker in text for marker in ELECTRIC_MARKERS):
        return False
    if any(marker in text for marker in HYBRID_OR_ICE_MARKERS):
        return False
    return True


def is_pure_electric_listing(item: dict[str, Any]) -> bool:
    if int(item.get("manual_electric") or 0):
        return True
    make, model = listing_make_model(item)
    if is_electric_make_model(make, model):
        return True
    return is_pure_electric_fuel(item.get("fuel"))


def _electric_make_model_sql() -> str:
    from autoplius.title_sql import title_make_expr, title_model_expr

    make_expr = f"lower({title_make_expr()})"
    model_expr = f"lower({title_model_expr()})"
    parts: list[str] = []
    for make, model in sorted(ELECTRIC_MAKE_MODELS, key=lambda pair: pair[0].casefold()):
        folded_model = model.casefold()
        model_checks = [
            f"{model_expr} = '{folded_model}'",
            f"{model_expr} LIKE '{folded_model} %'",
        ]
        if folded_model == "i3":
            model_checks.append(f"{model_expr} LIKE 'i3s%'")
        parts.append(
            f"({make_expr} = '{make.casefold()}' AND ({' OR '.join(model_checks)}))"
        )
    if not parts:
        return "0"
    return "(" + " OR ".join(parts) + ")"


def electric_sql_clause(*, include: bool) -> str:
    """SQLite expression: listing is (or is not) treated as pure electric.

    Note: SQLite lower() is ASCII-only, so Cyrillic markers are matched with
    literal substrings instead of lower(fuel). Latin markers avoid bare
    'elektr%' so city names like Elektrėnai are not treated as EVs.
    """
    auto = """(
        (
          COALESCE(fuel, '') LIKE '%лектр%'
          OR COALESCE(fuel, '') LIKE '%Лектр%'
          OR lower(COALESCE(fuel, '')) LIKE 'elektra%'
          OR lower(COALESCE(fuel, '')) LIKE 'electric%'
          OR lower(COALESCE(fuel, '')) LIKE 'electricity%'
        )
        AND COALESCE(fuel, '') NOT LIKE '%/%'
        AND COALESCE(fuel, '') NOT LIKE '%гибрид%'
        AND COALESCE(fuel, '') NOT LIKE '%Гибрид%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%hybrid%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%plug-in%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%plugin%'
        AND COALESCE(fuel, '') NOT LIKE '%бенз%'
        AND COALESCE(fuel, '') NOT LIKE '%Бенз%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%benzin%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%byenzin%'
        AND COALESCE(fuel, '') NOT LIKE '%дизел%'
        AND COALESCE(fuel, '') NOT LIKE '%Дизел%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%dizel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%dyzel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%diesel%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%petrol%'
        AND lower(COALESCE(fuel, '')) NOT LIKE '%gasoline%'
    )"""
    known = _electric_make_model_sql()
    expr = f"(COALESCE(manual_electric, 0) = 1 OR {auto} OR {known})"
    return expr if include else f"NOT {expr}"
