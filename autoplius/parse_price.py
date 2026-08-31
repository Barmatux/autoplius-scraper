from __future__ import annotations

import re
from typing import Any

PRICE_RE = re.compile(r"([\d\s]+)\s*€")

NET_VAT_MARKERS = (
    "be pvm",
    "без ндс",
    "pvm išskiriamas",
    "pvm isk",
)
GROSS_VAT_MARKERS = (
    "su pvm",
    "с ндс",
)


def parse_price_amount(text: str | None) -> int | None:
    if not text:
        return None
    match = PRICE_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def _vat_kind(note_lower: str) -> str | None:
    if any(marker in note_lower for marker in NET_VAT_MARKERS):
        return "net"
    if any(marker in note_lower for marker in GROSS_VAT_MARKERS):
        return "gross"
    return None


def _clean_vat_note(subtitle: str) -> str | None:
    note = PRICE_RE.sub("", subtitle).strip(" /-|,")
    note = re.sub(r"\s+", " ", note).strip()
    return note or None


def parse_listing_prices(
    *,
    main_text: str | None,
    subtitle_text: str | None = None,
) -> dict[str, Any]:
    """Parse Autoplius main price + optional VAT subtitle."""
    main = parse_price_amount(main_text)
    subtitle = (subtitle_text or "").strip()
    sub_amount = parse_price_amount(subtitle) if subtitle else None

    result: dict[str, Any] = {
        "price_eur": main,
        "price_net_eur": None,
        "price_gross_eur": None,
        "price_vat_note": _clean_vat_note(subtitle) if subtitle else None,
    }

    if sub_amount is None:
        return result

    kind = _vat_kind(subtitle.lower())
    if kind == "net":
        result["price_net_eur"] = sub_amount
        if main is not None and main != sub_amount:
            result["price_gross_eur"] = main
            result["price_eur"] = main
        elif main is None:
            result["price_eur"] = sub_amount
    elif kind == "gross":
        result["price_gross_eur"] = sub_amount
        if main is not None and main != sub_amount:
            result["price_net_eur"] = main
            result["price_eur"] = sub_amount
        elif main is None:
            result["price_eur"] = sub_amount

    return result
