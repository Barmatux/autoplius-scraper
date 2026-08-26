#!/usr/bin/env python3
"""Import all JSON snapshots into SQLite."""

from __future__ import annotations

import argparse
import json
import sys

from scraper.config import Settings
from scraper.db import db_stats, import_snapshots, init_db
from scraper.logging_setup import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Autoplius JSON snapshots into SQLite")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    setup_logging(settings.logs_dir, verbose=args.verbose)
    init_db(settings.db_path)
    result = import_snapshots(settings.db_path, settings.data_dir)
    stats = db_stats(settings.db_path)
    print(json.dumps({"import": result, "stats": stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
