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
from scraper.listing_query import backfill_engine_liters, backfill_mileage_km

settings = Settings.from_env()
print("backfill_engine_liters:", backfill_engine_liters(settings.db_path))
print("backfill_mileage_km:", backfill_mileage_km(settings.db_path))
PY

echo "=== exchange rates ==="
echo "Rates are refreshed by GitHub Actions into SQLite (exchange_rates table)."

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
