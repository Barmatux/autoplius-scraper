"""Known exact displacements for VAG petrol/diesel engines (VW / Audi / SEAT).

Listing labels often round to 1.0 / 1.4 / 1.6 L; Belarus customs needs the real cm³.
Skoda shares the same engines but is out of scope until explicitly enabled.
"""

from __future__ import annotations

import re

VAG_MAKES = frozenset({"volkswagen", "vw", "audi", "seat"})

# Nominal → real cm³ (personal import / catalog hints).
VAG_ENGINE_CM3 = {
    "1.0_tsi": 999,
    "1.2_i": 1197,
    "1.2_tdi": 1199,
    "1.4_i_122": 1390,
    "1.4_i_125": 1395,
    "1.4_tsi": 1395,
    "1.5_i": 1498,
    "1.8_tsi": 1798,
    "1.4_tdi": 1422,
    "1.6_tdi": 1598,
    "1.9_tdi": 1896,
}

_LITERS_RE = re.compile(r"(?<!\d)(\d+[.,]\d+)(?!\d)")
_HP_RE = re.compile(r"(?<!\d)(122|125)\s*(?:a\.?\s*g\.?|hp|ps|л\.?\s*с\.?)?\b", re.I)
_KW_RE = re.compile(r"(?<!\d)(90|92)\s*k\s*w\b", re.I)
_DIESEL_RE = re.compile(r"\b(tdi|tdci|diesel|dyzel|дизел|дизель)\b", re.I)
_PETROL_TURBO_RE = re.compile(r"\b(tsi|tfsi|turbo)\b", re.I)
_PETROL_I_RE = re.compile(r"(?<![a-z])i(?![a-z])|\bmpi\b|\bfsi\b", re.I)


def normalize_vag_make(make: str | None) -> str | None:
    folded = (make or "").casefold().strip()
    if not folded:
        return None
    if folded in {"vw", "volkswagen", "volkswagen ag"}:
        return "volkswagen"
    if folded.startswith("audi"):
        return "audi"
    if folded.startswith("seat"):
        return "seat"
    return None


def is_vag_make(make: str | None) -> bool:
    return normalize_vag_make(make) is not None


def _liters_token(text: str) -> str | None:
    match = _LITERS_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    # Canonical one-decimal token used in map keys: 1.0, 1.2, …
    return f"{value:.1f}"


def _fuel_kind(engine_label: str, fuel: str | None) -> str:
    blob = f"{engine_label} {fuel or ''}"
    if _DIESEL_RE.search(blob):
        return "diesel"
    if _PETROL_TURBO_RE.search(blob) or _PETROL_I_RE.search(blob):
        return "petrol"
    fuel_folded = (fuel or "").casefold()
    if any(m in fuel_folded for m in ("dizel", "diesel", "дизел")):
        return "diesel"
    if any(m in fuel_folded for m in ("benzin", "petrol", "gasoline", "бенз")):
        return "petrol"
    return "unknown"


def _hp_hint(text: str) -> int | None:
    match = _HP_RE.search(text)
    if match:
        return int(match.group(1))
    match = _KW_RE.search(text)
    if not match:
        return None
    kw = int(match.group(1))
    if kw == 90:
        return 122
    if kw == 92:
        return 125
    return None


def vag_customs_cm3(
    make: str | None,
    engine_label: str | None,
    fuel: str | None = None,
) -> int | None:
    """Return exact cm³ for a VAG engine label, or None if unknown."""
    if not is_vag_make(make):
        return None
    label = (engine_label or "").strip()
    if not label or label == "—":
        return None

    liters = _liters_token(label)
    if liters is None:
        return None
    kind = _fuel_kind(label, fuel)
    hp = _hp_hint(label)

    if liters == "1.0" and kind != "diesel":
        return VAG_ENGINE_CM3["1.0_tsi"]
    if liters == "1.2":
        if kind == "diesel":
            return VAG_ENGINE_CM3["1.2_tdi"]
        return VAG_ENGINE_CM3["1.2_i"]
    if liters == "1.4":
        if kind == "diesel":
            return VAG_ENGINE_CM3["1.4_tdi"]
        if hp == 125:
            return VAG_ENGINE_CM3["1.4_i_125"]
        if hp == 122:
            return VAG_ENGINE_CM3["1.4_i_122"]
        # 1.4 TSI/TFSI on the market are usually EA211 1395; plain 1.4i → 1390.
        if _PETROL_TURBO_RE.search(label):
            return VAG_ENGINE_CM3["1.4_tsi"]
        return VAG_ENGINE_CM3["1.4_i_122"]
    if liters == "1.5" and kind != "diesel":
        return VAG_ENGINE_CM3["1.5_i"]
    if liters == "1.8" and kind != "diesel":
        return VAG_ENGINE_CM3["1.8_tsi"]
    if liters == "1.6" and kind == "diesel":
        return VAG_ENGINE_CM3["1.6_tdi"]
    if liters == "1.9" and kind == "diesel":
        return VAG_ENGINE_CM3["1.9_tdi"]
    return None
