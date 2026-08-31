#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoplius-scraper}"
PY="$APP_DIR/.venv/bin/python"
LOCK_FILE="${TARGET_SCRAPE_LOCK_FILE:-/var/lock/autoplius-target-scrape.lock}"

cd "$APP_DIR"

# Deep scrape of Roman's priority models (12 filtered queries).
exec flock -n "$LOCK_FILE" "$PY" run_target_scrape.py "$@"
