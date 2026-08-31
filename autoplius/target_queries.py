from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoplius.search_query import FUEL_DIESEL, SearchQuery

MAKE_SLUGS: dict[str, str] = {
    "Peugeot": "peugeot",
    "Nissan": "nissan",
    "Renault": "renault",
    "Hyundai": "hyundai",
    "Kia": "kia",
    "Ford": "ford",
}

MODEL_SLUGS: dict[str, dict[str, str]] = {
    "Peugeot": {"3008": "3008", "5008": "5008"},
    "Nissan": {"Qashqai": "qashqai"},
    "Renault": {"Grand Scenic": "grand-scenic"},
    "Hyundai": {"i40": "i40"},
    "Kia": {"Optima": "optima"},
    "Ford": {"S-Max": "s-max", "Galaxy": "galaxy"},
}


@dataclass(frozen=True)
class TargetModelSpec:
    make: str
    model: str
    year_from: int | None = None
    year_to: int | None = None
    diesel_only: bool = False


def build_target_queries(*, root: Path | None = None) -> list[SearchQuery]:
    """Expand Roman's target list into concrete Autoplius search queries."""
    _ = root  # reserved for future overrides
    specs: list[TargetModelSpec] = [
        TargetModelSpec("Peugeot", "3008", 2011, 2015, diesel_only=True),
        TargetModelSpec("Peugeot", "3008", 2016, None, diesel_only=False),
        TargetModelSpec("Peugeot", "5008", 2011, 2015, diesel_only=True),
        TargetModelSpec("Peugeot", "5008", 2016, None, diesel_only=False),
        TargetModelSpec("Nissan", "Qashqai", 2010, 2017, diesel_only=True),
        TargetModelSpec("Nissan", "Qashqai", 2018, None, diesel_only=False),
        TargetModelSpec("Renault", "Grand Scenic", 2010, 2017, diesel_only=True),
        TargetModelSpec("Renault", "Grand Scenic", 2018, None, diesel_only=False),
        TargetModelSpec("Hyundai", "i40", None, None, diesel_only=True),
        TargetModelSpec("Kia", "Optima", None, None, diesel_only=True),
        TargetModelSpec("Ford", "S-Max", 2011, None, diesel_only=True),
        TargetModelSpec("Ford", "Galaxy", 2011, None, diesel_only=True),
    ]

    queries: list[SearchQuery] = []
    for spec in specs:
        make_slug = MAKE_SLUGS.get(spec.make)
        model_slug = (MODEL_SLUGS.get(spec.make) or {}).get(spec.model)
        if not make_slug or not model_slug:
            raise KeyError(f"Missing slug mapping for {spec.make} {spec.model}")
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
                make_slug=make_slug,
                model_slug=model_slug,
                year_from=spec.year_from,
                year_to=spec.year_to,
                fuel_ids=fuel_ids,
            )
        )
    return queries


def query_summary(queries: list[SearchQuery]) -> list[dict[str, Any]]:
    return [{"label": q.label, **q.build_kwargs()} for q in queries]
