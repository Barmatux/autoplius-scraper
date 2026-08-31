from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from autoplius.urls import get_base_url, search_path

CATEGORY_USED_CARS = 2
FUEL_PETROL = 30
FUEL_DIESEL = 32


@dataclass(frozen=True)
class SearchQuery:
    """One Autoplius search request using RU slug paths (/peugeot/3008)."""

    label: str
    make_slug: str
    model_slug: str
    year_from: int | None = None
    year_to: int | None = None
    fuel_ids: tuple[int, ...] = ()
    extra: dict[str, str | int] = field(default_factory=dict)

    def build_url(self, *, page: int = 1, base_url: str | None = None) -> str:
        base = (base_url or get_base_url()).rstrip("/")
        path = f"{search_path(base_url)}/{self.make_slug}/{self.model_slug}"
        params: dict[str, str | int] = {
            "page_nr": page,
            "category_id": CATEGORY_USED_CARS,
        }
        if self.year_from is not None:
            params["make_date_from"] = self.year_from
        if self.year_to is not None:
            params["make_date_to"] = self.year_to
        for fuel_id in self.fuel_ids:
            params[f"fuel_id[{fuel_id}]"] = fuel_id
        params.update(self.extra)
        return f"{base}{path}?{urlencode(params)}"

    def build_kwargs(self) -> dict[str, object]:
        """Summary payload for logging/CLI."""
        return {
            "make_slug": self.make_slug,
            "model_slug": self.model_slug,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "fuel_ids": list(self.fuel_ids),
            "url_example": self.build_url(page=1),
        }
