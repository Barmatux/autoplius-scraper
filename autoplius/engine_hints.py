"""Exact displacement hints from the customs «Объем ДВС» table.

Used for catalog `suggested_cm3` only — the operator still confirms via Save.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Rounded listing cm³ → liters family.
_ROUNDED_CM3_TO_LITERS = {
    875: "0.9",
    898: "0.9",
    900: "0.9",
    995: "1.0",
    996: "1.0",
    998: "1.0",
    999: "1.0",
    1000: "1.0",
    1084: "1.1",
    1100: "1.1",
    1120: "1.1",
    1124: "1.1",
    1149: "1.2",
    1193: "1.2",
    1197: "1.2",
    1198: "1.2",
    1199: "1.2",
    1200: "1.2",
    1206: "1.2",
    1240: "1.2",
    1242: "1.2",
    1248: "1.3",
    1300: "1.3",
    1332: "1.3",
    1339: "1.3",
    1349: "1.3",
    1364: "1.4",
    1368: "1.4",
    1388: "1.4",
    1390: "1.4",
    1395: "1.4",
    1396: "1.4",
    1397: "1.4",
    1398: "1.4",
    1399: "1.4",
    1400: "1.4",
    1422: "1.4",
    1461: "1.5",
    1477: "1.5",
    1482: "1.5",
    1490: "1.5",
    1496: "1.5",
    1497: "1.5",
    1498: "1.5",
    1499: "1.5",
    1500: "1.5",
    1560: "1.6",
    1580: "1.6",
    1582: "1.6",
    1590: "1.6",
    1591: "1.6",
    1596: "1.6",
    1597: "1.6",
    1598: "1.6",
    1600: "1.6",
    1618: "1.6",
    1685: "1.7",
    1686: "1.7",
    1700: "1.7",
    1749: "1.7",
    1753: "1.8",
    1796: "1.8",
    1798: "1.8",
    1799: "1.8",
    1800: "1.8",
    1870: "1.9",
    1896: "1.9",
    1900: "1.9",
    1995: "2.0",
    2000: "2.0",
}

_LITERS_RE = re.compile(r"(?<!\d)(\d+[.,]\d+)\s*(?:l|л)?(?!\d)", re.I)
_CM3_RE = re.compile(r"(?<!\d)(\d{3,4})\s*(?:cm|см)(?:³|3|\u00b3)?", re.I)
_BARE_CM3_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
_HP_RE = re.compile(
    r"(?<!\d)(122|124|125)\s*(?:a\.?\s*g\.?|hp|ps|л\.?\s*с\.?)?\b",
    re.I,
)
_KW_RE = re.compile(r"(?<!\d)(77|90|92|103|110|124|135|150)\s*k\s*[wв]\b", re.I)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DIESEL_RE = re.compile(
    r"\b(tdi|tdci|cdti|crdi|hdi|cdi|multijet|diesel|dyzel|дизел|дизель|\bd\b)\b",
    re.I,
)
_PETROL_TURBO_RE = re.compile(
    r"\b(tsi|tfsi|tce|t-jet|tgdi|t-gdi|gdi|dig-?t|puretech|ecoboost|turbo)\b",
    re.I,
)
_PETROL_I_RE = re.compile(r"(?<![a-zа-я])i(?![a-zа-я])|\bmpi\b|\bfsi\b", re.I)

FAMILY_MAKES: dict[str, frozenset[str]] = {
    "bmw_mini": frozenset({"bmw", "mini"}),
    "vag": frozenset({"audi", "volkswagen", "vw", "seat"}),
    "stellantis": frozenset({"peugeot", "citroen", "citroën", "ds", "ds automobiles"}),
    "renault_nissan": frozenset({"renault", "nissan", "dacia"}),
    "opel_gm": frozenset({"opel", "chevrolet", "buick", "gmc", "vauxhall"}),
    "fiat_jeep": frozenset({"fiat", "jeep", "abarth", "alfa romeo", "alfa"}),
    "ford": frozenset({"ford"}),
    "honda": frozenset({"honda"}),
    "hyundai_kia": frozenset({"hyundai", "kia"}),
    "mazda": frozenset({"mazda"}),
    "mercedes": frozenset({"mercedes", "mercedes-benz", "mercedes benz"}),
    "mitsubishi": frozenset({"mitsubishi"}),
    "suzuki": frozenset({"suzuki"}),
    "toyota": frozenset({"toyota", "lexus"}),
    "volvo": frozenset({"volvo"}),
}


@dataclass(frozen=True)
class _Rule:
    family: str
    liters: str
    fuel: str  # petrol | diesel | any
    cm3: int
    priority: int = 10
    require_any: tuple[str, ...] = ()
    require_all: tuple[str, ...] = ()
    exclude_any: tuple[str, ...] = ()
    require_hp: tuple[int, ...] = ()
    require_kw: tuple[int, ...] = ()
    model_any: tuple[str, ...] = ()
    year_min: int | None = None
    year_max: int | None = None


def _rules() -> tuple[_Rule, ...]:
    return (
        # --- BMW / MINI ---
        _Rule("bmw_mini", "1.6", "diesel", 1598, 40, require_any=("n47",)),
        _Rule("bmw_mini", "2.0", "diesel", 1995, 40, require_any=("n47",)),
        _Rule("bmw_mini", "1.5", "diesel", 1496, 30, require_any=("b37",)),
        _Rule("bmw_mini", "1.2", "petrol", 1198, 30, require_any=("b38",)),
        _Rule("bmw_mini", "1.5", "petrol", 1499, 30, require_any=("b38",)),
        _Rule("bmw_mini", "1.6", "petrol", 1598, 30, require_any=("ep6",)),
        _Rule("bmw_mini", "1.6", "diesel", 1598, 5),
        _Rule("bmw_mini", "2.0", "diesel", 1995, 5),
        _Rule("bmw_mini", "1.5", "diesel", 1496, 5),
        _Rule("bmw_mini", "1.2", "petrol", 1198, 5),
        _Rule("bmw_mini", "1.5", "petrol", 1499, 5),
        _Rule("bmw_mini", "1.6", "petrol", 1598, 5),
        # --- VAG ---
        _Rule("vag", "1.0", "petrol", 999, 20, require_any=("tsi", "tfsi")),
        _Rule("vag", "1.0", "petrol", 999, 5),
        _Rule("vag", "1.2", "diesel", 1199, 20),
        _Rule("vag", "1.2", "petrol", 1197, 10),
        _Rule("vag", "1.4", "diesel", 1422, 20),
        _Rule("vag", "1.4", "petrol", 1395, 40, require_hp=(125,)),
        _Rule("vag", "1.4", "petrol", 1395, 40, require_kw=(92,)),
        _Rule("vag", "1.4", "petrol", 1390, 40, require_hp=(122,)),
        _Rule("vag", "1.4", "petrol", 1390, 40, require_kw=(90,)),
        _Rule("vag", "1.4", "petrol", 1395, 25, require_any=("tsi", "tfsi")),
        _Rule("vag", "1.4", "petrol", 1390, 5),
        _Rule("vag", "1.5", "petrol", 1498, 10),
        _Rule("vag", "1.6", "petrol", 1598, 10),
        _Rule("vag", "1.6", "diesel", 1598, 10),
        _Rule("vag", "1.8", "petrol", 1798, 10),
        _Rule("vag", "1.9", "diesel", 1896, 10),
        # --- Stellantis ---
        _Rule("stellantis", "1.1", "petrol", 1124, 10),
        _Rule("stellantis", "1.2", "petrol", 1199, 20, require_any=("puretech", "pure tech")),
        _Rule("stellantis", "1.2", "petrol", 1199, 5),
        _Rule("stellantis", "1.4", "diesel", 1398, 20, require_any=("hdi",)),
        _Rule("stellantis", "1.4", "diesel", 1398, 5),
        _Rule("stellantis", "1.5", "diesel", 1499, 10),
        _Rule("stellantis", "1.6", "petrol", 1598, 20, require_any=("ep6",)),
        _Rule("stellantis", "1.6", "petrol", 1598, 5),
        _Rule("stellantis", "1.3", "petrol", 1332, 10),
        _Rule("stellantis", "1.3", "diesel", 1248, 20, require_any=("multijet",)),
        _Rule("stellantis", "1.3", "diesel", 1248, 5),
        _Rule("stellantis", "1.8", "diesel", 1798, 10),
        # --- Renault / Nissan / Dacia ---
        _Rule("renault_nissan", "0.9", "petrol", 898, 20, require_any=("tce", "tce")),
        _Rule("renault_nissan", "0.9", "petrol", 898, 5),
        _Rule("renault_nissan", "1.0", "petrol", 996, 25, require_any=("mpi",)),
        _Rule("renault_nissan", "1.0", "petrol", 999, 20, require_any=("tce",)),
        _Rule("renault_nissan", "1.0", "petrol", 999, 5),
        _Rule("renault_nissan", "1.1", "petrol", 1149, 30, model_any=("twingo",)),
        _Rule("renault_nissan", "1.2", "petrol", 1149, 30, model_any=("twingo",)),
        _Rule("renault_nissan", "1.2", "petrol", 1199, 30, model_any=("austral",)),
        _Rule("renault_nissan", "1.2", "petrol", 1240, 25, require_any=("mpi",)),
        _Rule("renault_nissan", "1.2", "petrol", 1197, 20, require_any=("tce",)),
        _Rule("renault_nissan", "1.2", "petrol", 1197, 5),
        _Rule("renault_nissan", "1.4", "petrol", 1397, 20, require_any=("tce",)),
        _Rule("renault_nissan", "1.4", "petrol", 1397, 5),
        _Rule(
            "renault_nissan",
            "1.5",
            "petrol",
            1461,
            40,
            require_any=("e-power", "epower", "e power"),
            model_any=("qashqai",),
        ),
        _Rule(
            "renault_nissan",
            "1.5",
            "petrol",
            1497,
            40,
            require_any=("e-power", "epower", "e power"),
            model_any=("x-trail", "xtrail", "x trail"),
        ),
        _Rule("renault_nissan", "1.5", "diesel", 1461, 10),
        _Rule("renault_nissan", "1.6", "petrol", 1618, 30, require_any=("dig-t", "digt", "dig t")),
        _Rule("renault_nissan", "1.6", "petrol", 1598, 10),
        _Rule("renault_nissan", "1.6", "diesel", 1598, 10),
        _Rule("renault_nissan", "1.7", "diesel", 1749, 10),
        _Rule("renault_nissan", "1.9", "diesel", 1870, 10),
        # --- Opel / GM ---
        _Rule("opel_gm", "1.0", "petrol", 995, 10),
        _Rule("opel_gm", "1.2", "petrol", 1199, 30, require_any=("psa", "puretech")),
        _Rule("opel_gm", "1.2", "petrol", 1206, 20, require_any=("gm",)),
        _Rule("opel_gm", "1.2", "petrol", 1206, 5),
        _Rule("opel_gm", "1.4", "petrol", 1364, 40, require_kw=(103,)),
        _Rule("opel_gm", "1.4", "petrol", 1399, 40, require_kw=(92,)),
        _Rule("opel_gm", "1.4", "petrol", 1398, 20, model_any=("ampera",)),
        _Rule("opel_gm", "1.4", "petrol", 1398, 5),
        _Rule("opel_gm", "1.5", "petrol", 1490, 20, model_any=("volt", "insignia")),
        _Rule("opel_gm", "1.5", "petrol", 1490, 5),
        _Rule("opel_gm", "1.5", "diesel", 1496, 30, require_any=("cdti",), model_any=("astra",)),
        _Rule("opel_gm", "1.5", "diesel", 1499, 20, require_any=("hdi", "psa")),
        _Rule("opel_gm", "1.5", "diesel", 1496, 5),
        _Rule("opel_gm", "1.6", "petrol", 1598, 10),
        _Rule("opel_gm", "1.8", "petrol", 1796, 10),
        _Rule("opel_gm", "1.3", "diesel", 1248, 20, require_any=("multijet", "cdti")),
        _Rule("opel_gm", "1.3", "diesel", 1248, 5),
        _Rule("opel_gm", "1.6", "diesel", 1598, 10),
        _Rule("opel_gm", "1.7", "diesel", 1686, 10),
        # --- Fiat / Jeep ---
        _Rule("fiat_jeep", "0.9", "petrol", 875, 10),
        _Rule("fiat_jeep", "1.2", "petrol", 1242, 10),
        _Rule("fiat_jeep", "1.4", "petrol", 1368, 20, require_any=("t-jet", "tjet", "t jet")),
        _Rule("fiat_jeep", "1.4", "petrol", 1368, 5),
        _Rule("fiat_jeep", "1.3", "diesel", 1248, 20, require_any=("multijet",)),
        _Rule("fiat_jeep", "1.3", "diesel", 1248, 5),
        _Rule("fiat_jeep", "1.6", "diesel", 1598, 20, require_any=("multijet",)),
        _Rule("fiat_jeep", "1.6", "diesel", 1598, 5),
        # --- Ford ---
        _Rule("ford", "1.0", "petrol", 999, 20, require_any=("ecoboost",)),
        _Rule("ford", "1.0", "petrol", 999, 5),
        _Rule("ford", "1.1", "petrol", 1084, 10),
        _Rule("ford", "1.4", "petrol", 1388, 10),
        _Rule(
            "ford",
            "1.5",
            "petrol",
            1499,
            40,
            require_kw=(124,),
            model_any=("fusion",),
        ),
        _Rule("ford", "1.5", "petrol", 1499, 30, model_any=("fusion",), require_any=("usa",)),
        _Rule("ford", "1.5", "petrol", 1498, 20, require_any=("ecoboost",)),
        _Rule("ford", "1.5", "petrol", 1498, 5),
        _Rule("ford", "1.6", "petrol", 1596, 10),
        _Rule("ford", "1.8", "petrol", 1798, 10),
        _Rule("ford", "1.4", "diesel", 1398, 10),
        _Rule("ford", "1.5", "diesel", 1499, 10),
        _Rule("ford", "1.8", "diesel", 1753, 10),
        # --- Honda ---
        _Rule("honda", "1.3", "petrol", 1339, 10),
        _Rule("honda", "1.4", "petrol", 1339, 10),
        _Rule("honda", "1.5", "petrol", 1498, 10),
        _Rule("honda", "1.8", "petrol", 1799, 10),
        _Rule("honda", "1.6", "diesel", 1597, 10),
        # --- Hyundai / Kia ---
        _Rule("hyundai_kia", "1.0", "petrol", 998, 20, require_any=("t-gdi", "tgdi", "gdi")),
        _Rule("hyundai_kia", "1.0", "petrol", 998, 5),
        _Rule("hyundai_kia", "1.2", "petrol", 1248, 30, year_max=2019),
        _Rule("hyundai_kia", "1.2", "petrol", 1197, 20, year_min=2020),
        _Rule("hyundai_kia", "1.2", "petrol", 1197, 5),  # default: newer
        _Rule("hyundai_kia", "1.4", "petrol", 1368, 30, year_max=2014),
        _Rule("hyundai_kia", "1.4", "petrol", 1396, 20, year_min=2015),
        _Rule("hyundai_kia", "1.4", "petrol", 1396, 5),
        _Rule("hyundai_kia", "1.5", "petrol", 1482, 20, require_any=("t-gdi", "tgdi", "gdi")),
        _Rule("hyundai_kia", "1.5", "petrol", 1482, 5),
        _Rule("hyundai_kia", "1.6", "petrol", 1580, 40, model_any=("ioniq", "niro")),
        _Rule(
            "hyundai_kia",
            "1.6",
            "petrol",
            1598,
            35,
            require_any=("t-gdi", "tgdi", "hybrid", "гибрид"),
        ),
        _Rule("hyundai_kia", "1.6", "petrol", 1591, 10, require_any=("mpi",)),
        _Rule("hyundai_kia", "1.6", "petrol", 1591, 5),
        _Rule("hyundai_kia", "1.1", "diesel", 1120, 10),
        _Rule("hyundai_kia", "1.4", "diesel", 1396, 10),
        _Rule("hyundai_kia", "1.6", "diesel", 1582, 20, require_any=("old", "старый")),
        _Rule("hyundai_kia", "1.6", "diesel", 1598, 5),  # default: newer
        _Rule("hyundai_kia", "1.7", "diesel", 1685, 10),
        # --- Mazda ---
        _Rule("mazda", "1.3", "petrol", 1349, 10),
        _Rule("mazda", "1.8", "petrol", 1798, 10),
        _Rule("mazda", "1.5", "diesel", 1499, 10),
        # --- Mercedes ---
        _Rule(
            "mercedes",
            "1.5",
            "petrol",
            1497,
            40,
            require_kw=(135,),
            require_any=("w205",),
        ),
        _Rule(
            "mercedes",
            "1.5",
            "petrol",
            1496,
            40,
            require_kw=(150,),
            require_any=("w206", "hybrid", "гибрид"),
        ),
        _Rule("mercedes", "1.5", "petrol", 1497, 10),
        _Rule("mercedes", "1.8", "petrol", 1796, 10),
        _Rule("mercedes", "1.6", "diesel", 1598, 20, require_any=("r9m",), model_any=("vito",)),
        _Rule("mercedes", "1.6", "diesel", 1598, 5),
        _Rule("mercedes", "1.8", "diesel", 1796, 10),
        # --- Mitsubishi ---
        _Rule("mitsubishi", "1.2", "petrol", 1193, 10),
        _Rule("mitsubishi", "1.5", "petrol", 1499, 10),
        _Rule("mitsubishi", "1.6", "petrol", 1590, 10),
        _Rule("mitsubishi", "1.8", "diesel", 1798, 10),
        # --- Suzuki ---
        _Rule("suzuki", "1.9", "diesel", 1870, 10),
        # --- Toyota / Lexus ---
        _Rule("toyota", "1.5", "petrol", 1490, 20, require_any=("hybrid", "гибрид")),
        _Rule("toyota", "1.5", "petrol", 1490, 5),
        _Rule("toyota", "1.8", "petrol", 1798, 20, require_any=("hybrid", "гибрид")),
        _Rule("toyota", "1.8", "petrol", 1798, 5),
        _Rule("toyota", "1.4", "diesel", 1364, 10),
        # --- Volvo ---
        _Rule("volvo", "1.5", "petrol", 1477, 25, require_any=("hybrid", "гибрид")),
        _Rule("volvo", "1.5", "petrol", 1498, 20, require_any=("t", "turbo")),
        _Rule("volvo", "1.5", "petrol", 1498, 5),
        _Rule("volvo", "1.6", "petrol", 1596, 10),
        _Rule("volvo", "1.6", "diesel", 1560, 10),
    )


_RULES = _rules()


def normalize_hint_family(make: str | None) -> str | None:
    folded = (make or "").casefold().strip()
    if not folded:
        return None
    if folded in {"vw", "volkswagen", "volkswagen ag"}:
        return "vag"
    if folded.startswith("audi"):
        return "vag"
    if folded.startswith("seat"):
        return "vag"
    if folded.startswith("mercedes"):
        return "mercedes"
    if folded.startswith("citro"):
        return "stellantis"
    if folded.startswith("alfa"):
        return "fiat_jeep"
    if folded in {"ds", "ds automobiles"} or folded.startswith("ds "):
        return "stellantis"
    for family, makes in FAMILY_MAKES.items():
        if folded in makes:
            return family
        for candidate in makes:
            if folded.startswith(candidate):
                return family
    return None


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
    if any(
        m in fuel_folded
        for m in ("benzin", "petrol", "gasoline", "бенз", "hybrid", "гибрид", "электри")
    ):
        return "petrol"
    return "unknown"


def _hp_hint(text: str) -> int | None:
    match = _HP_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def _kw_hint(text: str) -> int | None:
    match = _KW_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def _years(text: str) -> list[int]:
    return [int(y) for y in _YEAR_RE.findall(text)]


def _contains_any(blob: str, markers: tuple[str, ...]) -> bool:
    return any(m in blob for m in markers)


def hint_customs_cm3(
    make: str | None,
    engine_label: str | None,
    fuel: str | None = None,
    model: str | None = None,
) -> int | None:
    """Return exact cm³ from the customs table, or None if unknown/ambiguous."""
    family = normalize_hint_family(make)
    if family is None:
        return None
    label = (engine_label or "").strip()
    if not label or label == "—":
        return None

    liters = _liters_token(label)
    if liters is None:
        # Ford «EcoBoost» alone → 1.0 / 999 when no other volume.
        blob = label.casefold()
        if family == "ford" and "ecoboost" in blob and not _LITERS_RE.search(label):
            liters = "1.0"
        else:
            return None

    kind = _fuel_kind(label, fuel)
    blob = f"{label} {fuel or ''} {model or ''}".casefold()
    hp = _hp_hint(label)
    kw = _kw_hint(label)
    years = _years(f"{label} {model or ''}")

    best: _Rule | None = None
    for rule in _RULES:
        if rule.family != family or rule.liters != liters:
            continue
        if rule.fuel != "any" and kind != "unknown" and kind != rule.fuel:
            continue
        if rule.require_any and not _contains_any(blob, rule.require_any):
            continue
        if rule.require_all and not all(m in blob for m in rule.require_all):
            continue
        if rule.exclude_any and _contains_any(blob, rule.exclude_any):
            continue
        if rule.require_hp and (hp is None or hp not in rule.require_hp):
            continue
        if rule.require_kw and (kw is None or kw not in rule.require_kw):
            continue
        if rule.model_any:
            model_blob = (model or "").casefold()
            if not _contains_any(f"{model_blob} {blob}", rule.model_any):
                continue
        if rule.year_min is not None or rule.year_max is not None:
            if not years:
                # Year-gated rule without a year in the label — skip (fall to default).
                continue
            year = max(years)
            if rule.year_min is not None and year < rule.year_min:
                continue
            if rule.year_max is not None and year > rule.year_max:
                continue
        if best is None or rule.priority > best.priority:
            best = rule

    return best.cm3 if best else None
