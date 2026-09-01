#!/usr/bin/env bash
# Idempotent post-deploy steps (safe to re-run on every deploy).
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
PY="${DEPLOY_PY:-$APP/.venv/bin/python}"

cd "$APP"

echo "=== backfill engine_liters ==="
sudo -u autoplius "$PY" - <<'PY'
import sys
from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
sys.path.insert(0, str(ROOT))
from scraper.config import Settings
from scraper.listing_query import backfill_engine_liters

updated = backfill_engine_liters(Settings.from_env().db_path)
print("backfill_engine_liters:", updated)
PY

if [[ -f deploy/nginx-autoplius-ui.conf ]]; then
  echo "=== nginx config ==="
  sudo cp deploy/nginx-autoplius-ui.conf /etc/nginx/sites-available/autoplius-ui
  sudo ln -sf /etc/nginx/sites-available/autoplius-ui /etc/nginx/sites-enabled/autoplius-ui
  sudo nginx -t
  sudo systemctl reload nginx
fi

echo "=== post-deploy complete ==="
