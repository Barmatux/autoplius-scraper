#!/usr/bin/env python3
"""Restore VM UI app.py from stash snapshot and re-apply admin routes from git."""
from __future__ import annotations

import re
from pathlib import Path

APP = Path("/opt/autoplius-scraper/ui/app.py")
STASHED = Path("/tmp/stashed_app.py")
GIT = Path("/tmp/git_app.py")


def extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def replace_auth(merged: str, git_app: str) -> str:
    auth_block = extract_block(git_app, "def _admin_credentials(", "def db_path(")
    merged = re.sub(
        r"def _check_basic_auth\(\).*?"
        r'@app\.before_request\s*\n'
        r"def require_auth\(\):.*?"
        r'\{"WWW-Authenticate": \'Basic realm="Autoplius Scraper"\'\},\s*\)\s*\n',
        auth_block,
        merged,
        count=1,
        flags=re.DOTALL,
    )
    if "def require_admin_auth(" not in merged:
        insert_at = merged.index("def db_path(")
        merged = merged[:insert_at] + auth_block + merged[insert_at:]
    return merged


def replace_admin_block(merged: str, git_app: str) -> str:
    admin_block = extract_block(git_app, "def _admin_status_filter(", '@app.get("/api/listings")')
    marker = '@app.get("/api/listings")'
    if "def _admin_status_filter(" in merged:
        merged = re.sub(
            r"def _admin_status_filter\(.*?"
            + re.escape(marker),
            admin_block + marker,
            merged,
            count=1,
            flags=re.DOTALL,
        )
    elif "def admin_listings" not in merged:
        merged = merged.replace(marker, admin_block + marker, 1)
    return merged


def patch_imports(merged: str) -> str:
    if "import json" not in merged.splitlines()[:8]:
        merged = merged.replace("import os\n", "import json\nimport os\n", 1)
    if "set_listing_archived" not in merged:
        merged = merged.replace(
            "    update_listing_admin,\n",
            "    update_listing_admin,\n    set_listing_archived,\n",
            1,
        )
    if "update_listing_admin" not in merged:
        merged = merged.replace(
            "    scrape_runs_analytics,\n",
            "    scrape_runs_analytics,\n    update_listing_admin,\n    set_listing_archived,\n",
            1,
        )
    if "TAB_ADMIN" not in merged:
        merged = merged.replace(
            'TAB_ARCHIVED = "archived"\n',
            'TAB_ARCHIVED = "archived"\nTAB_ADMIN = "admin"\nADMIN_PAGE_SIZE = 50\n',
            1,
        )
    return merged


def main() -> int:
    if not STASHED.is_file():
        raise SystemExit(f"missing {STASHED}")
    if not APP.is_file():
        raise SystemExit(f"missing {APP}")
    if not GIT.is_file():
        raise SystemExit(f"missing {GIT}; run: git show HEAD:ui/app.py > /tmp/git_app.py")

    stashed = STASHED.read_text(encoding="utf-8")
    git_app = GIT.read_text(encoding="utf-8")

    merged = patch_imports(stashed)
    merged = replace_auth(merged, git_app)
    merged = replace_admin_block(merged, git_app)

    APP.write_text(merged, encoding="utf-8")
    print("OK merged", APP)
    print("engine_kpp_lines", "engine_kpp_lines" in merged)
    print("require_admin_auth", "def require_admin_auth(" in merged)
    print("admin_archive_listing", "def admin_archive_listing(" in merged)
    print("set_listing_archived import", "set_listing_archived" in merged.split("from scraper.db import")[1][:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
