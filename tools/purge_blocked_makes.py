#!/usr/bin/env python3
"""Archive Skoda, Ligier/Microcar, pickups and remove them from engine catalog."""
from __future__ import annotations

import argparse
from pathlib import Path

from scraper.config import Settings
from scraper.db import default_db_path, init_db, purge_blocked_makes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(Settings.from_env().data_dir),
        help="Path to autoplius SQLite database",
    )
    args = parser.parse_args()
    init_db(args.db)
    result = purge_blocked_makes(args.db)
    print(
        "Purged hidden listings: "
        f"archived_listings={result['archived_listings']} "
        f"(blocked={result.get('archived_blocked_makes', 0)}, "
        f"pickups={result.get('archived_pickups', 0)}) "
        f"catalog_removed={result['catalog_removed']}"
    )


if __name__ == "__main__":
    main()
