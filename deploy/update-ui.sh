#!/usr/bin/env bash
set -euo pipefail
APP=/opt/autoplius-scraper
cd "$APP"
sudo -u autoplius git pull --ff-only origin main
sudo -u autoplius "$APP/.venv/bin/pip" install -q -r requirements.txt
sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart autoplius-ui.service
sleep 1
sudo systemctl is-active autoplius-ui.service
curl -s -o /dev/null -w "local_http=%{http_code}\n" http://127.0.0.1:8080/ || true
