#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/autoplius-scraper}"
PY="$APP_DIR/.venv/bin/python"

cd "$APP_DIR"
exec "$PY" run_scrape.py
