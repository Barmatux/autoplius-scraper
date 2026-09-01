#!/usr/bin/env python3
"""Restore VM UI app.py from stash snapshot and re-apply admin routes from git."""
from __future__ import annotations

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
    if "def _check_basic_auth(" in merged:
        start = merged.index("def _check_basic_auth(")
        end = merged.index("@app.context_processor", start)
        merged = merged[:start] + auth_block + merged[end:]
    elif "def require_admin_auth(" in merged and "def admin_enter(" not in merged:
        start = merged.index("def _admin_credentials(")
        end = merged.index("@app.context_processor", start)
        merged = merged[:start] + auth_block + merged[end:]
    elif "def require_admin_auth(" not in merged:
        insert_at = merged.index("def db_path(")
        merged = merged[:insert_at] + auth_block + merged[insert_at:]
    return merged


def replace_admin_block(merged: str, git_app: str) -> str:
    admin_block = extract_block(git_app, '@app.get("/admin/listings")', '@app.get("/api/listings")')
    marker = '@app.get("/api/listings")'
    for start_marker in ('def _admin_status_filter(', '@app.get("/admin/listings")'):
        if start_marker in merged:
            start = merged.index(start_marker)
            end = merged.index(marker, start)
            merged = merged[:start] + admin_block + merged[end:]
            return merged
    if "def admin_listings" not in merged:
        merged = merged.replace(marker, admin_block + marker, 1)
    return merged


def patch_imports(merged: str) -> str:
    if "import json" not in merged.splitlines()[:8]:
        merged = merged.replace("import os\n", "import json\nimport os\n", 1)
    if ", session," not in merged and " session," not in merged:
        merged = merged.replace("request, Response,", "request, Response, session,", 1)
    if "app.secret_key" not in merged:
        merged = merged.replace(
            'app.config["DB_PATH"] = Path(os.environ.get("DB_PATH", default_db_path(DEFAULT_DATA_DIR)))\n',
            'app.config["DB_PATH"] = Path(os.environ.get("DB_PATH", default_db_path(DEFAULT_DATA_DIR)))\n'
            "app.secret_key = (\n"
            '    os.environ.get("FLASK_SECRET_KEY")\n'
            '    or os.environ.get("ADMIN_PASSWORD")\n'
            '    or os.environ.get("UI_PASSWORD")\n'
            '    or "autoplius-dev-secret-change-me"\n'
            ")\n",
            1,
        )
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
    print("admin_enter", "def admin_enter(" in merged)
    print("set_listing_archived import", "set_listing_archived" in merged.split("from scraper.db import")[1][:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
