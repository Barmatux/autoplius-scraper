from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SearchListingPreview:
    autoplius_id: int
    url: str
    title: str
    year: str | None = None
    body_type: str | None = None
    price_eur: int | None = None
    price_net_eur: int | None = None
    price_gross_eur: int | None = None
    price_vat_note: str | None = None
    fuel: str | None = None
    transmission: str | None = None
    engine: str | None = None
    mileage_km: int | None = None
    city: str | None = None
    photo_url: str | None = None
    has_vin_badge: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ListingDetail:
    autoplius_id: int
    url: str
    title: str
    price_eur: int | None = None
    price_net_eur: int | None = None
    price_gross_eur: int | None = None
    price_vat_note: str | None = None
    description: str | None = None
    phone: str | None = None
    vin_masked: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    photo_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
