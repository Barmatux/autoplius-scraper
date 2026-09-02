from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autoplius.price_rb import PriceRbBreakdown, estimate_price_rb

LABEL_NET_EXPORT = "Цена без НДС (Экспорт)"
LABEL_GROSS = "Цена с НДС"


def format_eur(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", " ") + " €"


@dataclass(frozen=True)
class CatalogPriceLine:
    label: str | None
    lt_formatted: str
    rb: PriceRbBreakdown | None


def _vat_price_pairs(item: dict[str, Any]) -> list[tuple[str, int]] | None:
    net = item.get("price_net_eur")
    gross = item.get("price_gross_eur")
    main = item.get("price_eur")

    if gross is not None and net is not None and gross != net:
        return [
            (LABEL_NET_EXPORT, int(net)),
            (LABEL_GROSS, int(gross)),
        ]

    if net is not None and main is not None and main != net:
        return [
            (LABEL_NET_EXPORT, int(net)),
            (LABEL_GROSS, int(main)),
        ]

    if gross is not None and main is not None and main != gross:
        return [
            (LABEL_NET_EXPORT, int(main)),
            (LABEL_GROSS, int(gross)),
        ]

    return None


def catalog_price_lines(
    item: dict[str, Any],
    *,
    privilege_usd: float | int | None = None,
    delivery_usd: float | int | None = None,
) -> list[CatalogPriceLine]:
    pairs = _vat_price_pairs(item)
    if pairs:
        return [
            CatalogPriceLine(
                label=label,
                lt_formatted=format_eur(price_eur),
                rb=estimate_price_rb(
                    item,
                    price_eur=price_eur,
                    privilege_usd=privilege_usd,
                    delivery_usd=delivery_usd,
                ),
            )
            for label, price_eur in pairs
        ]

    main = item.get("price_eur")
    if main is not None:
        return [
            CatalogPriceLine(
                label=None,
                lt_formatted=format_eur(int(main)),
                rb=estimate_price_rb(
                    item,
                    privilege_usd=privilege_usd,
                    delivery_usd=delivery_usd,
                ),
            )
        ]

    return [CatalogPriceLine(label=None, lt_formatted="—", rb=None)]


def price_lt_lines(item: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (label, formatted price) lines for LT column/detail."""
    return [(line.label or "", line.lt_formatted) for line in catalog_price_lines(item)]
