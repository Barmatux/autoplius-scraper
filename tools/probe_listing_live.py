#!/usr/bin/env python3
"""CLI helper: print available|unavailable|unknown for one Autoplius listing URL."""

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
    if not url:
        print("unknown")
        return 2
    status = probe_listing_http(url)
    if status == "unknown":
        status = _probe_listing_browser_inline(url)
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
