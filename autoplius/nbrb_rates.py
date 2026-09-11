"""Official National Bank of Belarus (nbrb.by) exchange rates."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_API = "https://www.nbrb.by/api/exrates/rates/{code}"
_CACHE: dict[str, dict[str, object]] = {}
_CACHE_TTL = timedelta(minutes=30)

# NBRB currency letter codes we care about on the calculator board.
NBRB_CODES = ("USD", "EUR")


@dataclass(frozen=True)
class NbrbRateRow:
    code: str
    rate: float
    scale: int
    date: str
    prev_rate: float | None
    delta: float | None
    direction: str  # up | down | flat | unknown

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _parse_rate_payload(payload: dict[str, Any]) -> tuple[float, int, str]:
    scale = int(payload.get("Cur_Scale") or 1) or 1
    official = float(payload["Cur_OfficialRate"])
    per_unit = official / scale
    raw_date = str(payload.get("Date") or "")
    day = raw_date[:10] if raw_date else ""
    return per_unit, scale, day


def fetch_nbrb_rate(code: str, *, on_date: date | None = None) -> tuple[float, int, str]:
    """Return (BYN per 1 unit, scale, YYYY-MM-DD)."""
    url = _API.format(code=code.upper()) + "?parammode=2"
    if on_date is not None:
        url += f"&ondate={on_date.isoformat()}"
    return _parse_rate_payload(_fetch_json(url))


def _direction(today: float, yesterday: float | None) -> tuple[float | None, str]:
    if yesterday is None:
        return None, "unknown"
    delta = today - yesterday
    if abs(delta) < 1e-9:
        return 0.0, "flat"
    if delta > 0:
        return delta, "up"
    return delta, "down"


def get_nbrb_board(*, force: bool = False) -> list[NbrbRateRow]:
    """Today's USD/EUR official rates with vs-yesterday direction."""
    cache_key = "board"
    now = datetime.now(timezone.utc)
    cached = _CACHE.get(cache_key) or {}
    cached_at = cached.get("fetched_at")
    cached_rows = cached.get("rows")
    if (
        not force
        and isinstance(cached_at, datetime)
        and isinstance(cached_rows, list)
        and now - cached_at < _CACHE_TTL
    ):
        return list(cached_rows)  # type: ignore[arg-type]

    today = date.today()
    yesterday = today - timedelta(days=1)
    rows: list[NbrbRateRow] = []
    for code in NBRB_CODES:
        try:
            rate, scale, day = fetch_nbrb_rate(code)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            rows.append(
                NbrbRateRow(
                    code=code,
                    rate=0.0,
                    scale=1,
                    date="",
                    prev_rate=None,
                    delta=None,
                    direction="unknown",
                )
            )
            continue
        prev_rate: float | None
        try:
            prev_rate, _, _ = fetch_nbrb_rate(code, on_date=yesterday)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            prev_rate = None
        delta, direction = _direction(rate, prev_rate)
        rows.append(
            NbrbRateRow(
                code=code,
                rate=round(rate, 4),
                scale=scale,
                date=day or today.isoformat(),
                prev_rate=None if prev_rate is None else round(prev_rate, 4),
                delta=None if delta is None else round(delta, 4),
                direction=direction,
            )
        )

    _CACHE[cache_key] = {"fetched_at": now, "rows": rows}
    return rows
