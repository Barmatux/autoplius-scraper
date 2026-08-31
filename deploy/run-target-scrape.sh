#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoplius-scraper}"
PY="$APP_DIR/.venv/bin/python"
LOCK_FILE="${TARGET_SCRAPE_LOCK_FILE:-/var/lock/autoplius-target-scrape.lock}"

cd "$APP_DIR"

# Discover/refresh make+model IDs, then run the deep target scrape.
exec flock -n "$LOCK_FILE" bash -lc "
  set -euo pipefail
  cd '$APP_DIR'
  '$PY' tools/discover_catalog_ids.py --output data/catalog_ids.json || true
  exec '$PY' run_target_scrape.py \"\$@\"
" _ "$@"
