#!/usr/bin/env python3
"""Nightly Autoplius reconcile: deep search (A) + live-probe archive (B)."""

from __future__ import annotations

import argparse
import json
import sys

from scraper.config import Settings
from scraper.logging_setup import setup_logging
from scraper.nightly_reconcile import run_nightly_reconcile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nightly deep search + live-probe reconcile for stale active listings",
    )
    parser.add_argument(
        "--skip-deep-search",
        action="store_true",
        help="Skip phase A (paginate search until empty)",
    )
    parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="Skip phase B (probe stale active URLs)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    setup_logging(settings.logs_dir, verbose=args.verbose)
    summary = run_nightly_reconcile(
        settings,
        skip_deep_search=args.skip_deep_search,
        skip_probe=args.skip_probe,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
