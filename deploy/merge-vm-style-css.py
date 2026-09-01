#!/usr/bin/env python3
"""Restore VM style.css from stash and keep admin styles from git."""
from __future__ import annotations

from pathlib import Path

CSS = Path("/opt/autoplius-scraper/ui/static/style.css")
STASHED = Path("/tmp/stashed_style.css")
GIT = Path("/tmp/git_style.css")


def main() -> int:
    if not STASHED.is_file():
        raise SystemExit(f"missing {STASHED}")
    merged = STASHED.read_text(encoding="utf-8")

    admin_marker = ".admin-filters"
    if GIT.is_file():
        git_css = GIT.read_text(encoding="utf-8")
        start = git_css.find(admin_marker)
        if start != -1:
            git_admin = git_css[start:].lstrip()
            if admin_marker in merged:
                merged_start = merged.find(admin_marker)
                merged = merged[:merged_start].rstrip() + "\n\n" + git_admin
            else:
                merged = merged.rstrip() + "\n\n" + git_admin

    CSS.write_text(merged, encoding="utf-8")
    print("OK", CSS, "bytes", len(merged.encode("utf-8")))
    print("vehicle-hierarchy", "vehicle-hierarchy" in merged)
    print("admin-form", ".admin-form" in merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
