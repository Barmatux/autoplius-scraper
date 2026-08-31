#!/usr/bin/env bash
set -euo pipefail

APP=/opt/autoplius-scraper
cd "$APP"

sudo -u autoplius "$APP/.venv/bin/pip" install -q -r requirements.txt

echo "=== Sync listing photos to MinIO ==="
sudo -u autoplius bash -c "cd $APP && set -a && source .env && set +a && $APP/.venv/bin/python sync_photos.py $*"

echo "=== Restart UI ==="
sudo systemctl restart autoplius-ui.service
sleep 1
curl -s -o /dev/null -w "ui=%{http_code}\n" http://127.0.0.1:8080/
