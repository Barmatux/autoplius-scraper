"""Known exact displacements for VAG petrol/diesel engines (VW / Audi / SEAT).

Delegates to the shared customs table matcher in ``engine_hints``.
"""

from __future__ import annotations

from autoplius.engine_hints import hint_customs_cm3, normalize_hint_family

VAG_MAKES = frozenset({"volkswagen", "vw", "audi", "seat"})


def normalize_vag_make(make: str | None) -> str | None:
    if normalize_hint_family(make) != "vag":
        return None
    folded = (make or "").casefold().strip()
    if folded in {"vw", "volkswagen", "volkswagen ag"}:
        return "volkswagen"
    if folded.startswith("audi"):
        return "audi"
    if folded.startswith("seat"):
        return "seat"
    return None


def is_vag_make(make: str | None) -> bool:
    return normalize_vag_make(make) is not None


def vag_customs_cm3(
    make: str | None,
    engine_label: str | None,
    fuel: str | None = None,
) -> int | None:
    """Return exact cm³ for a VAG engine label, or None if unknown."""
    if not is_vag_make(make):
        return None
    return hint_customs_cm3(make, engine_label, fuel)
