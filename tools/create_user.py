#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.db import create_user, default_db_path, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a personal cabinet user.")
    parser.add_argument("username", help="Login name (min 3 characters)")
    parser.add_argument("password", help="Plain-text password (stored hashed in SQLite)")
    parser.add_argument("--display-name", help="Optional display name in the cabinet")
    args = parser.parse_args()

    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    db_path = Path(os.environ.get("DB_PATH", default_db_path(data_dir)))
    init_db(db_path)
    user = create_user(
        db_path,
        args.username,
        args.password,
        display_name=args.display_name,
    )
    print(f"created user id={user['id']} username={user['username']}")


if __name__ == "__main__":
    main()
