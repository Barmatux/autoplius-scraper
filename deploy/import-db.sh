#!/usr/bin/env bash
set -euo pipefail
APP=/opt/autoplius-scraper
cd "$APP"
sudo -u autoplius git pull --ff-only origin main
sudo -u autoplius bash -lc "cd $APP && DATA_DIR=/var/lib/autoplius-scraper/data DB_PATH=/var/lib/autoplius-scraper/data/autoplius.db .venv/bin/python import_to_db.py"
sudo chown autoplius:autoplius /var/lib/autoplius-scraper/data/autoplius.db*
# ensure env has DB_PATH
if ! sudo grep -q '^DB_PATH=' "$APP/.env"; then
  echo 'DB_PATH=/var/lib/autoplius-scraper/data/autoplius.db' | sudo tee -a "$APP/.env" >/dev/null
fi
sudo systemctl restart autoplius-ui.service
sleep 1
curl -s http://127.0.0.1:8080/api/db/stats
echo
sudo systemctl is-active autoplius-ui.service
