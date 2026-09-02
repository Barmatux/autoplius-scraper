"""Quick-filter presets for popular import models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

DIESEL_FUEL = "Дизель"


@dataclass(frozen=True)
class ImportPreset:
    label: str
    make: str
    model: str = ""
    year_from: int | None = None
    year_to: int | None = None
    fuels: tuple[str, ...] = (DIESEL_FUEL,)
    volume_from: float | None = None
    volume_to: float | None = None


IMPORT_PRESETS: tuple[ImportPreset, ...] = (
    ImportPreset(
        label="Peugeot 3008 1.6 HDI 2011-",
        make="Peugeot",
        model="3008",
        year_from=2011,
        year_to=2016,
        volume_from=1.6,
        volume_to=1.6,
    ),
    ImportPreset(
        label="Peugeot 5008 1.6 HDI 2011-",
        make="Peugeot",
        model="5008",
        year_from=2011,
        year_to=2016,
        volume_from=1.6,
        volume_to=1.6,
    ),
    ImportPreset(
        label="Citroen C4 Grand Picasso 1.6 HDI 2013-",
        make="Citroen",
        model="Grand C4 Picasso",
        year_from=2013,
        year_to=2017,
        volume_from=1.6,
        volume_to=1.6,
    ),
    ImportPreset(
        label="Volvo 1.6 HDI 2011-",
        make="Volvo",
        year_from=2011,
        year_to=2017,
    ),
    ImportPreset(
        label="Nissan Qashqai 1.5 dci",
        make="Nissan",
        model="Qashqai",
        volume_from=1.5,
        volume_to=1.5,
    ),
)


def preset_query_pairs(preset: ImportPreset) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = [
        ("tab", "all"),
        ("sort", "added_desc"),
        ("page", "1"),
        ("make", preset.make),
    ]
    if preset.model:
        pairs.append(("model", preset.model))
    if preset.year_from is not None:
        pairs.append(("year_from", str(preset.year_from)))
    if preset.year_to is not None:
        pairs.append(("year_to", str(preset.year_to)))
    for fuel in preset.fuels:
        pairs.append(("fuel", fuel))
    if preset.volume_from is not None:
        pairs.append(("volume_from", _format_volume(preset.volume_from)))
    if preset.volume_to is not None:
        pairs.append(("volume_to", _format_volume(preset.volume_to)))
    return pairs


def _format_volume(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"


def preset_query_string(preset: ImportPreset) -> str:
    return urlencode(preset_query_pairs(preset))


def preset_links(index_path: str = "/") -> list[dict[str, Any]]:
    base = index_path.rstrip("/") or "/"
    return [
        {
            "label": preset.label,
            "href": f"{base}?{preset_query_string(preset)}",
        }
        for preset in IMPORT_PRESETS
    ]
