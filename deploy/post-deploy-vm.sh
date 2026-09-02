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

echo "=== refresh myfin rates (best effort) ==="
if sudo -u autoplius env PYTHONPATH="$APP" DATA_DIR=/var/lib/autoplius-scraper/data "$PY" tools/refresh_myfin_rates.py; then
  echo "myfin rates refreshed"
else
  echo "WARNING: myfin refresh failed; using cached/fallback rates"
fi

echo "=== media cache dir ==="
mkdir -p /var/lib/autoplius-scraper/media-cache
chown autoplius:autoplius /var/lib/autoplius-scraper/media-cache

if [[ -f deploy/nginx-autoplius-ui.conf ]]; then
  echo "=== nginx config ==="
  sudo cp deploy/nginx-autoplius-ui.conf /etc/nginx/sites-available/autoplius-ui
  sudo ln -sf /etc/nginx/sites-available/autoplius-ui /etc/nginx/sites-enabled/autoplius-ui
  if sudo nginx -t; then
    sudo systemctl reload nginx
  else
    echo "WARNING: nginx -t failed (often unrelated site SSL config); autoplius site updated but nginx not reloaded"
  fi
fi

echo "=== post-deploy complete ==="
