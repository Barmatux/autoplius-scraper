#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoplius-scraper}"
PY="$APP_DIR/.venv/bin/python"
# Share lock with incremental scraper so browser profile is not contested.
LOCK_FILE="${SCRAPE_LOCK_FILE:-/var/lock/autoplius-scraper.lock}"
LOG_DIR="${LOGS_DIR:-/var/log/autoplius-scraper}"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"
exec flock -n "$LOCK_FILE" "$PY" run_nightly_reconcile.py "$@" >>"$LOG_DIR/nightly-reconcile.log" 2>&1
