"""Lithuanian city helpers: distance from Vilnius and Google Maps links."""

from __future__ import annotations

from urllib.parse import quote

VILNIUS_ALIASES = frozenset({"вильнюс", "vilnius"})

# Approximate road distances from Vilnius, km (rounded).
# Sources: common road tables / Google driving distance ranges.
DISTANCES_FROM_VILNIUS_KM: dict[str, int] = {
    # Russian localized names
    "вильнюс": 0,
    "каунас": 100,
    "клайпеда": 310,
    "шяуляй": 210,
    "паневежис": 140,
    "алитус": 105,
    "марьямполе": 140,
    "утена": 95,
    "тельшяи": 270,
    "йонава": 55,
    "кедайняи": 90,
    "таураге": 230,
    "мажейкяй": 290,
    "плунге": 285,
    "кретинга": 320,
    "паланга": 330,
    "друскиникаи": 130,
    "рокишкис": 150,
    "радвилишкис": 180,
    "укмерге": 75,
    "электренай": 50,
    "висагинас": 150,
    "гаргждай": 300,
    "шилуте": 290,
    # Lithuanian spellings still present in DB
    "vilnius": 0,
    "kaunas": 100,
    "klaipėda": 310,
    "klaipeda": 310,
    "šiauliai": 210,
    "siauliai": 210,
    "panevėžys": 140,
    "panevezys": 140,
    "alytus": 105,
    "marijampolė": 140,
    "marijampole": 140,
    "utena": 95,
    "telšiai": 270,
    "telsiai": 270,
    "jonava": 55,
    "kėdainiai": 90,
    "kedainiai": 90,
    "tauragė": 230,
    "taurage": 230,
    "mažeikiai": 290,
    "mazeikiai": 290,
    "plungė": 285,
    "plunge": 285,
    "kretinga": 320,
    "palanga": 330,
    "druskininkai": 130,
    "rokiškis": 150,
    "rokiskis": 150,
    "radviliškis": 180,
    "radviliskis": 180,
    "ukmergė": 75,
    "ukmerge": 75,
    "elektrėnai": 50,
    "elektrenai": 50,
    "visaginas": 150,
    "gargždai": 300,
    "gargzdai": 300,
    "šilutė": 290,
    "silute": 290,
    "kaišiadorys": 70,
    "kaisiadorys": 70,
    "кайшядорис": 70,
    "raseiniai": 160,
    "расейняй": 160,
    "vievis": 40,
    "вевис": 40,
    "vilkaviškis": 160,
    "vilkaviskis": 160,
    "вилкавишкис": 160,
    "prienai": 100,
    "пренай": 100,
    "ignalina": 110,
    "игналина": 110,
    "jurbarkas": 180,
    "юрбаркас": 180,
    "varėna": 90,
    "varena": 90,
    "варена": 90,
    "širvintos": 50,
    "sirvintos": 50,
    "ширвинтос": 50,
    "trakai": 30,
    "тракай": 30,
    "birštonas": 95,
    "birstonas": 95,
    "бирштонас": 95,
    "joniškis": 200,
    "joniskis": 200,
    "ионишкис": 200,
    "kelmė": 200,
    "kelme": 200,
    "кельме": 200,
    "kupiškis": 140,
    "kupiskis": 140,
    "купишкис": 140,
    "lazdijai": 140,
    "лаздияй": 140,
    "molėtai": 65,
    "moletai": 65,
    "молетай": 65,
    "nemenčinė": 20,
    "nemencine": 20,
    "неменчине": 20,
    "pasvalys": 170,
    "пасвалис": 170,
}


def _norm(city: str | None) -> str:
    if not city:
        return ""
    return (
        city.strip()
        .casefold()
        .replace("š", "s")
        .replace("č", "c")
        .replace("ž", "z")
        .replace("ė", "e")
        .replace("ų", "u")
        .replace("ū", "u")
        .replace("į", "i")
        .replace("ą", "a")
    )


def _lookup_distance(city: str | None) -> int | None:
    if not city:
        return None
    raw = city.strip().casefold()
    if raw in DISTANCES_FROM_VILNIUS_KM:
        return DISTANCES_FROM_VILNIUS_KM[raw]
    folded = _norm(city)
    for key, value in DISTANCES_FROM_VILNIUS_KM.items():
        if _norm(key) == folded:
            return value
    return None


def is_vilnius(city: str | None) -> bool:
    if not city:
        return False
    return _norm(city) in {_norm(alias) for alias in VILNIUS_ALIASES}


def distance_from_vilnius_km(city: str | None) -> int | None:
    if is_vilnius(city):
        return None
    km = _lookup_distance(city)
    if km is None or km <= 0:
        return None
    return km


def distance_from_vilnius_label(city: str | None) -> str | None:
    km = distance_from_vilnius_km(city)
    if km is None:
        return None
    return f"({km} км от Вильнюса)"


def google_maps_url(city: str | None) -> str | None:
    if not city or not city.strip():
        return None
    query = quote(f"{city.strip()}, Lithuania")
    return f"https://www.google.com/maps/search/?api=1&query={query}"
