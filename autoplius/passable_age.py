from __future__ import annotations

import re
from datetime import date
from typing import Any

REG_DATE_RE = re.compile(r"(\d{4})(?:[-/](\d{1,2}))?")

PASSABLE_MIN_YEARS = 3
PASSABLE_MAX_YEARS = 5


def parse_registration_date(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    match = REG_DATE_RE.search(str(value).strip())
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    if month < 1 or month > 12:
        month = 1
    return year, month


def listing_age_months(item: dict[str, Any], *, today: date | None = None) -> int | None:
    parsed = parse_registration_date(item.get("year"))
    if parsed is None:
        params = item.get("parameters") or {}
        for key in ("Pirma registracija", "Первая регистрация", "Год выпуска"):
            parsed = parse_registration_date(params.get(key))
            if parsed:
                break
    if parsed is None:
        parsed = parse_registration_date(item.get("title"))
    if parsed is None:
        return None

    reg_year, reg_month = parsed
    today = today or date.today()
    return (today.year - reg_year) * 12 + (today.month - reg_month)


def is_passable_age(item: dict[str, Any], *, today: date | None = None) -> bool:
    months = listing_age_months(item, today=today)
    if months is None:
        return False
    years = months // 12
    return PASSABLE_MIN_YEARS <= years <= PASSABLE_MAX_YEARS


def is_older_than_years(
    item: dict[str, Any],
    *,
    years: int = 3,
    today: date | None = None,
) -> bool:
    """True when vehicle age is strictly greater than ``years`` (e.g. older than 3 years)."""
    months = listing_age_months(item, today=today)
    if months is None:
        return False
    return months > years * 12
