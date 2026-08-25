from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SearchListingPreview:
    autoplius_id: int
    url: str
    title: str
    year: str | None = None
    body_type: str | None = None
    price_eur: int | None = None
    fuel: str | None = None
    transmission: str | None = None
    engine: str | None = None
    mileage_km: int | None = None
    city: str | None = None
    photo_url: str | None = None
    has_vin_badge: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
