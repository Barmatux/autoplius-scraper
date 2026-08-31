#!/usr/bin/env bash
set -euo pipefail
APP=/opt/autoplius-scraper
cd "$APP"
sudo -u autoplius git pull --ff-only origin main
sudo -u autoplius "$APP/.venv/bin/pip" install -q -r requirements.txt
sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart autoplius-ui.service

# nginx on :80 -> flask :8080
if ! command -v nginx >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq nginx
fi
sudo cp "$APP/deploy/nginx-autoplius-ui.conf" /etc/nginx/sites-available/autoplius-ui
sudo ln -sfn /etc/nginx/sites-available/autoplius-ui /etc/nginx/sites-enabled/autoplius-ui
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 80/tcp || true
  sudo ufw allow 8080/tcp || true
fi

sleep 1
curl -s -o /dev/null -w "flask8080=%{http_code}\n" http://127.0.0.1:8080/
curl -s -o /dev/null -w "nginx80=%{http_code}\n" http://127.0.0.1/
sudo systemctl is-active autoplius-ui.service nginx
echo "Open http://84.252.139.137/  (need SG TCP 80) or SSH tunnel to :8080"
