from __future__ import annotations

from typing import Any


def format_eur(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", " ") + " €"


def price_lt_lines(item: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (label, formatted price) lines for LT column/detail."""
    net = item.get("price_net_eur")
    gross = item.get("price_gross_eur")
    main = item.get("price_eur")

    if gross is not None and net is not None and gross != net:
        return [
            ("с НДС", format_eur(gross)),
            ("без НДС", format_eur(net)),
        ]

    if net is not None and gross is None and main is not None and main != net:
        return [
            ("с НДС", format_eur(main)),
            ("без НДС", format_eur(net)),
        ]

    if gross is not None and net is None and main is not None:
        return [("", format_eur(main or gross))]

    if main is not None:
        return [("", format_eur(main))]

    return [("", "—")]
