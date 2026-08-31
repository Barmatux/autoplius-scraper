#!/usr/bin/env bash
set -euo pipefail
APP=/opt/autoplius-scraper
cd "$APP"
sudo -u autoplius git pull --ff-only origin main
sudo -u autoplius "$APP/.venv/bin/pip" install -q -r requirements.txt

# ensure enrich settings exist in .env
ensure_kv() {
  local key="$1" val="$2"
  if sudo grep -q "^${key}=" "$APP/.env"; then
    sudo sed -i "s|^${key}=.*|${key}=${val}|" "$APP/.env"
  else
    echo "${key}=${val}" | sudo tee -a "$APP/.env" >/dev/null
  fi
}
ensure_kv ENRICH_DETAILS true
ensure_kv ENRICH_LIMIT 0
ensure_kv DETAIL_DELAY_SEC 2

sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart autoplius-ui.service

echo "=== smoke: 1 search page, 3 details ==="
sudo -u autoplius bash -lc "cd $APP && .venv/bin/python run_scrape.py --pages 1 --enrich-limit 3"
echo "=== last_run ==="
sudo cat /var/lib/autoplius-scraper/data/last_run.json
echo
echo "=== sample listing keys ==="
sudo -u autoplius bash -lc "cd $APP && .venv/bin/python - <<'PY'
import json
from pathlib import Path
p=Path('/var/lib/autoplius-scraper/data/latest.json')
data=json.loads(p.read_text())
item=next(x for x in data['listings'] if x.get('detail_scraped'))
print('id', item['autoplius_id'])
print('phone', item.get('phone'))
print('vin', item.get('vin_masked'))
print('params', len(item.get('parameters') or {}))
print('photos', len(item.get('photo_urls') or []))
print('keys', sorted(item.keys()))
PY"
