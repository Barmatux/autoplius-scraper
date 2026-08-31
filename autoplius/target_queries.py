from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoplius.search_query import FUEL_DIESEL, SearchQuery

# Fallback IDs (overridden by data/catalog_ids.json when present).
FALLBACK_MAKES: dict[str, int] = {
    "Peugeot": 62,
    "Nissan": 73,
    "Renault": 88,
    "Hyundai": 35,
    "Kia": 52,
    "Ford": 29,
}

FALLBACK_MODELS: dict[str, dict[str, int]] = {
    "Peugeot": {"3008": 2989, "5008": 2990},
    "Nissan": {"Qashqai": 2876},
    "Renault": {"Grand Scenic": 2910, "Scenic": 2908},
    "Hyundai": {"i40": 2765},
    "Kia": {"Optima": 2845},
    "Ford": {"S-Max": 2650, "Galaxy": 2645},
}


@dataclass(frozen=True)
class TargetModelSpec:
    make: str
    model: str
    year_from: int | None = None
    year_to: int | None = None
    diesel_only: bool = False


def _load_catalog(root: Path) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    path = root / "data" / "catalog_ids.json"
    makes = dict(FALLBACK_MAKES)
    models = {make: dict(model_map) for make, model_map in FALLBACK_MODELS.items()}
    if not path.is_file():
        return makes, models
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return makes, models
    for name, make_id in (payload.get("makes") or {}).items():
        makes[str(name)] = int(make_id)
    for make_name, model_map in (payload.get("models_by_make") or {}).items():
        models[str(make_name)] = {str(k): int(v) for k, v in model_map.items()}
    return makes, models


def _resolve_model_id(
    models: dict[str, dict[str, int]],
    make: str,
    model: str,
) -> int | None:
    model_map = models.get(make) or {}
    if model in model_map:
        return model_map[model]
    needle = model.casefold()
    for name, model_id in model_map.items():
        if needle in name.casefold() or name.casefold() in needle:
            return model_id
    return None


def build_target_queries(*, root: Path | None = None) -> list[SearchQuery]:
    """Expand Roman's target list into concrete Autoplius search queries."""
    root = root or Path(__file__).resolve().parents[1]
    makes, models = _load_catalog(root)
    specs: list[TargetModelSpec] = [
        # Peugeot 3008/5008: 2011-2015 diesel; 2016+ all fuels
        TargetModelSpec("Peugeot", "3008", 2011, 2015, diesel_only=True),
        TargetModelSpec("Peugeot", "3008", 2016, None, diesel_only=False),
        TargetModelSpec("Peugeot", "5008", 2011, 2015, diesel_only=True),
        TargetModelSpec("Peugeot", "5008", 2016, None, diesel_only=False),
        # Nissan Qashqai: 2010-2017 diesel; 2018+ all
        TargetModelSpec("Nissan", "Qashqai", 2010, 2017, diesel_only=True),
        TargetModelSpec("Nissan", "Qashqai", 2018, None, diesel_only=False),
        # Renault Grand Scenic: 2010-2017 diesel; 2018+ all
        TargetModelSpec("Renault", "Grand Scenic", 2010, 2017, diesel_only=True),
        TargetModelSpec("Renault", "Grand Scenic", 2018, None, diesel_only=False),
        # Hyundai i40 / Kia Optima: diesel, all years
        TargetModelSpec("Hyundai", "i40", None, None, diesel_only=True),
        TargetModelSpec("Kia", "Optima", None, None, diesel_only=True),
        # Ford S-Max / Galaxy: from 2011 diesel
        TargetModelSpec("Ford", "S-Max", 2011, None, diesel_only=True),
        TargetModelSpec("Ford", "Galaxy", 2011, None, diesel_only=True),
    ]

    queries: list[SearchQuery] = []
    for spec in specs:
        make_id = makes.get(spec.make)
        model_id = _resolve_model_id(models, spec.make, spec.model)
        if make_id is None or model_id is None:
            raise KeyError(f"Missing catalog ID for {spec.make} {spec.model}")
        fuel_ids = (FUEL_DIESEL,) if spec.diesel_only else ()
        year_label = ""
        if spec.year_from and spec.year_to:
            year_label = f"{spec.year_from}-{spec.year_to}"
        elif spec.year_from:
            year_label = f"{spec.year_from}+"
        elif spec.year_to:
            year_label = f"-{spec.year_to}"
        fuel_label = "diesel" if spec.diesel_only else "all"
        queries.append(
            SearchQuery(
                label=f"{spec.make} {spec.model} {year_label} {fuel_label}".strip(),
                make_id=make_id,
                model_id=model_id,
                year_from=spec.year_from,
                year_to=spec.year_to,
                fuel_ids=fuel_ids,
            )
        )
    return queries


def query_summary(queries: list[SearchQuery]) -> list[dict[str, Any]]:
    return [
        {"label": q.label, **q.build_kwargs()}
        for q in queries
    ]
