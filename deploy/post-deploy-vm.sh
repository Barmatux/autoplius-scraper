#!/usr/bin/env bash
# Idempotent post-deploy steps (safe to re-run on every deploy).
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
PY="${DEPLOY_PY:-$APP/.venv/bin/python}"

cd "$APP"

echo "=== backfill engine_liters / mileage ==="
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

echo "=== purge blocked makes ==="
sudo -u autoplius "$PY" - <<'PY'
import sys
from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
sys.path.insert(0, str(ROOT))
from scraper.config import Settings
from scraper.db import purge_blocked_makes

result = purge_blocked_makes(Settings.from_env().db_path)
print("purge_blocked_makes:", result)
PY

echo "=== backfill localize (LT→RU body/fuel/etc) ==="
sudo -u autoplius "$PY" - <<'PY'
import sys
from pathlib import Path

ROOT = Path("/opt/autoplius-scraper")
sys.path.insert(0, str(ROOT))
from scraper.config import Settings
from tools.backfill_localize import backfill

db = Settings.from_env().db_path
print("backfill_localize:", backfill(db))
PY

echo "=== backfill description_ru (targeted + small missing batch) ==="
sudo -u autoplius "$PY" backfill_descriptions_ru.py --ids 32093378,32064212 || echo "WARNING: targeted description backfill failed"
sudo -u autoplius "$PY" backfill_descriptions_ru.py --limit 40 || echo "WARNING: description backfill batch failed"

echo "=== hybrid make+model report ==="
sudo -u autoplius "$PY" tools/list_hybrid_models.py || echo "WARNING: hybrid list failed"

echo "=== exchange rates ==="
echo "Rates are refreshed by GitHub Actions into SQLite (exchange_rates table)."

echo "=== media cache dir ==="
mkdir -p /var/lib/autoplius-scraper/media-cache
chown autoplius:autoplius /var/lib/autoplius-scraper/media-cache

if [[ -f deploy/ensure-nginx-bot-cache.sh ]]; then
  echo "=== nginx bot cache ==="
  bash deploy/ensure-nginx-bot-cache.sh || echo "WARNING: bot cache install failed"
fi

if [[ -f deploy/nginx-autoplius-ui.conf ]]; then
  echo "=== nginx config ==="
  CONF="deploy/nginx-autoplius-ui.conf"
  SITE="/etc/nginx/sites-available/autoplius-ui"
  # Never wipe a live Certbot HTTPS site with a partial/HTTP-only stub.
  if [[ -d /etc/letsencrypt/live/eu2.by ]] && [[ -f "$SITE" ]] && grep -qE 'listen[[:space:]]+\[?::\]?:?443|listen[[:space:]]+443' "$SITE"; then
    echo "SSL cert + live :443 site present — leaving $SITE unchanged"
    if ! grep -qE 'listen[[:space:]]+\[?::\]?:?443|listen[[:space:]]+443' "$CONF"; then
      echo "WARNING: $CONF is HTTP-only stub; not installing it. Keep full SSL conf in deploy/."
    fi
  elif grep -qE 'listen[[:space:]]+\[?::\]?:?443|listen[[:space:]]+443' "$CONF"; then
    sudo cp "$CONF" "$SITE"
    sudo ln -sf "$SITE" /etc/nginx/sites-enabled/autoplius-ui
  else
    echo "WARNING: refusing to install HTTP-only $CONF while production needs HTTPS"
  fi
  if sudo nginx -t; then
    sudo systemctl reload nginx
  else
    echo "WARNING: nginx -t failed (often unrelated site SSL config); autoplius site updated but nginx not reloaded"
  fi
fi

echo "=== post-deploy complete ==="
