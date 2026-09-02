#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autoplius.myfin_rates import (
    _db_path,
    apply_exchange_rates,
    fetch_myfin_pairs,
    refresh_myfin_rates,
)


def _resolve_db_path(raw: str | None) -> Path:
    if raw:
        return Path(raw)
    return _db_path()


def _load_pairs_json(raw: str) -> dict[str, float]:
    payload = json.loads(raw)
    if isinstance(payload, dict) and isinstance(payload.get("pairs"), dict):
        source = payload["pairs"]
    elif isinstance(payload, dict):
        source = payload
    else:
        raise ValueError("expected JSON object with exchange rate pairs")
    pairs: dict[str, float] = {}
    for key, value in source.items():
        if isinstance(value, dict) and "rate" in value:
            pairs[str(key)] = float(value["rate"])
        else:
            pairs[str(key)] = float(value)
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh myfin.by buy rates into SQLite.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fail if myfin.by cannot be fetched.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Fetch rates and print JSON to stdout without writing to the database.",
    )
    parser.add_argument(
        "--apply-json",
        help="Apply rates from a JSON file or '-' for stdin instead of fetching myfin.",
    )
    parser.add_argument(
        "--db-path",
        help="SQLite database path (defaults to DB_PATH env or DATA_DIR/autoplius.db).",
    )
    args = parser.parse_args()
    db_path = _resolve_db_path(args.db_path)

    if args.apply_json:
        raw = sys.stdin.read() if args.apply_json == "-" else Path(args.apply_json).read_text(encoding="utf-8")
        pairs = _load_pairs_json(raw)
        fetched_at = apply_exchange_rates(pairs, db_path)
        print(f"saved {len(pairs)} pairs to {db_path} at {fetched_at}")
        for pair, rate in pairs.items():
            print(f"{pair}={rate}")
        return

    if args.print_json:
        pairs = fetch_myfin_pairs(force=args.force)
        print(json.dumps({"pairs": pairs}, ensure_ascii=False))
        return

    rates = refresh_myfin_rates(db_path, force=args.force)
    print(f"saved to {db_path}")
    for pair, rate in rates.items():
        print(f"{pair}={rate}")


if __name__ == "__main__":
    main()
