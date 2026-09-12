"""Client for auto160 public Market Prices API.

See auto160 ``integrations/market/README.md``.

Env:
  AUTO160_MARKET_BASE_URL   default https://auto160.ru/api/v1/market
  MARKET_PRICES_API_KEY     same key as on auto160 (X-Api-Key)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class Auto160MarketError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def market_api_configured() -> bool:
    return bool((os.environ.get("MARKET_PRICES_API_KEY") or "").strip())


class Auto160MarketClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        timeout_sec: float = 2.5,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get("AUTO160_MARKET_BASE_URL")
            or "https://auto160.ru/api/v1/market"
        ).rstrip("/")
        self.api_key = (api_key or os.environ.get("MARKET_PRICES_API_KEY") or "").strip()
        self.timeout_sec = timeout_sec
        if not self.api_key:
            raise ValueError("MARKET_PRICES_API_KEY is required")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "X-Api-Key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "eu2-market-client/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", "replace")
                status = int(getattr(resp, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if exc.fp else ""
            raise Auto160MarketError(
                f"market API HTTP {exc.code}",
                status_code=exc.code,
                body=body,
            ) from exc
        except urllib.error.URLError as exc:
            raise Auto160MarketError(f"market API network error: {exc}") from exc
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise Auto160MarketError("market API returned non-JSON", status_code=status, body=raw) from exc
        if not isinstance(data, dict):
            raise Auto160MarketError("market API returned unexpected payload", status_code=status, body=raw)
        return data

    def lookup_avg_price(
        self,
        *,
        brand: str,
        model: str,
        year: int,
        window_days: int | None = 90,
        min_samples: int = 11,
    ) -> list[dict[str, Any]]:
        """GET /avg-prices/lookup — items for brand/model/year."""
        params: dict[str, Any] = {
            "brand": brand,
            "model": model,
            "year": year,
            "min_samples": min_samples,
        }
        if window_days is not None:
            params["window_days"] = window_days
        data = self._get("/avg-prices/lookup", params)
        items = data.get("items") or []
        return [item for item in items if isinstance(item, dict)]
