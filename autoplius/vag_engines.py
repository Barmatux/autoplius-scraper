"""Known exact displacements for VAG petrol/diesel engines (VW / Audi / SEAT).

Listing labels often round to 1.0 / 1.4 / 1.6 L or «1500 cm³»; Belarus customs needs the real cm³.
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
    "1.6_i": 1598,
    "1.8_tsi": 1798,
    "1.4_tdi": 1422,
    "1.6_tdi": 1598,
    "1.9_tdi": 1896,
}

# Rounded listing cm³ → liters family used by the map.
_ROUNDED_CM3_TO_LITERS = {
    999: "1.0",
    1000: "1.0",
    1197: "1.2",
    1198: "1.2",
    1199: "1.2",
    1200: "1.2",
    1390: "1.4",
    1395: "1.4",
    1400: "1.4",
    1422: "1.4",
    1498: "1.5",
    1500: "1.5",
    1598: "1.6",
    1600: "1.6",
    1798: "1.8",
    1800: "1.8",
    1896: "1.9",
    1900: "1.9",
}

_LITERS_RE = re.compile(r"(?<!\d)(\d+[.,]\d+)\s*(?:l|л)?(?!\d)", re.I)
_CM3_RE = re.compile(r"(?<!\d)(\d{3,4})\s*(?:cm|см)(?:³|3|\u00b3)?", re.I)
_BARE_CM3_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
_HP_RE = re.compile(
    r"(?<!\d)(122|125)\s*(?:a\.?\s*g\.?|hp|ps|л\.?\s*с\.?)?\b",
    re.I,
)
_KW_RE = re.compile(r"(?<!\d)(90|92)\s*k\s*[wв]\b", re.I)
_DIESEL_RE = re.compile(r"\b(tdi|tdci|diesel|dyzel|дизел|дизель)\b", re.I)
_PETROL_TURBO_RE = re.compile(r"\b(tsi|tfsi|turbo)\b", re.I)
_PETROL_I_RE = re.compile(r"(?<![a-zа-я])i(?![a-zа-я])|\bmpi\b|\bfsi\b", re.I)


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
    normalized = text.replace("\xa0", " ")
    match = _LITERS_RE.search(normalized)
    if match:
        raw = match.group(1).replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is not None and 0.5 <= value <= 10.0:
            return f"{value:.1f}"

    cm3 = None
    match = _CM3_RE.search(normalized)
    if match:
        cm3 = int(match.group(1))
    else:
        # Labels like «1500 cm³, 150 Л.С.» — first 3–4 digit volume before hp.
        match = _BARE_CM3_RE.search(normalized)
        if match:
            candidate = int(match.group(1))
            if 800 <= candidate <= 3000:
                cm3 = candidate
    if cm3 is None:
        return None
    return _ROUNDED_CM3_TO_LITERS.get(cm3)


def _fuel_kind(engine_label: str, fuel: str | None) -> str:
    blob = f"{engine_label} {fuel or ''}"
    if _DIESEL_RE.search(blob):
        return "diesel"
    if _PETROL_TURBO_RE.search(blob) or _PETROL_I_RE.search(blob):
        return "petrol"
    fuel_folded = (fuel or "").casefold()
    if any(m in fuel_folded for m in ("dizel", "diesel", "дизел")):
        return "diesel"
    if any(m in fuel_folded for m in ("benzin", "petrol", "gasoline", "бенз", "hybrid", "гибрид", "электри")):
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


def _cm3_for_liters(liters: str, *, kind: str, label: str, hp: int | None) -> int | None:
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
    if liters == "1.6":
        if kind == "diesel":
            return VAG_ENGINE_CM3["1.6_tdi"]
        if kind == "petrol":
            return VAG_ENGINE_CM3["1.6_i"]
        return None
    if liters == "1.9" and kind == "diesel":
        return VAG_ENGINE_CM3["1.9_tdi"]
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
    return _cm3_for_liters(liters, kind=kind, label=label, hp=hp)
