#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoplius-scraper}"
PY="$APP_DIR/.venv/bin/python"
LOCK_FILE="${SCRAPE_LOCK_FILE:-/var/lock/autoplius-scraper.lock}"

cd "$APP_DIR"
exec flock -n "$LOCK_FILE" "$PY" run_scrape.py
