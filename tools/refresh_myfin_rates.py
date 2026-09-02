#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autoplius.myfin_rates import _cache_file_path, refresh_myfin_rates


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh myfin.by buy rates for RB price calculation.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fail if myfin.by cannot be fetched instead of keeping cached/fallback values.",
    )
    args = parser.parse_args()
    rates = refresh_myfin_rates(force=args.force)
    print("saved", _cache_file_path())
    for pair, rate in rates.items():
        print(f"{pair}={rate}")


if __name__ == "__main__":
    main()
