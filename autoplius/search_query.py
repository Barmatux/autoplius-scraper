from __future__ import annotations

from dataclasses import dataclass, field

CATEGORY_USED_CARS = 2
FUEL_PETROL = 30
FUEL_DIESEL = 32


@dataclass(frozen=True)
class SearchQuery:
    """One Autoplius search request (make/model/year/fuel filters)."""

    label: str
    make_id: int
    model_id: int
    year_from: int | None = None
    year_to: int | None = None
    fuel_ids: tuple[int, ...] = ()
    extra: dict[str, str | int] = field(default_factory=dict)

    def build_kwargs(self) -> dict[str, object]:
        params: dict[str, str | int] = {"category_id": CATEGORY_USED_CARS}
        params.update(self.extra)
        for fuel_id in self.fuel_ids:
            params[f"fuel_id[{fuel_id}]"] = fuel_id
        return {
            "make_id": self.make_id,
            "model_id": self.model_id,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "extra": params,
        }
