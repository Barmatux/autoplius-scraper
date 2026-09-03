#!/usr/bin/env python3
"""CLI helper: print status[:reason] for one Autoplius listing URL."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoplius.listing_availability import (  # noqa: E402
    _probe_listing_browser_inline,
    probe_listing_http,
)


def main() -> int:
    url = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    listing_id = None
    if len(sys.argv) > 2:
        try:
            listing_id = int(sys.argv[2])
        except ValueError:
            listing_id = None
    if not url:
        print("unknown:http_error")
        return 2
    result = probe_listing_http(url, listing_id=listing_id)
    if result.status == "unknown":
        result = _probe_listing_browser_inline(url, listing_id=listing_id)
    print(f"{result.status}:{result.reason or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
