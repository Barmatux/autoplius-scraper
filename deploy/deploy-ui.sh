#!/usr/bin/env bash
set -euo pipefail

APP=/opt/autoplius-scraper

cd "$APP"
sudo -u autoplius git pull --ff-only origin main
sudo -u autoplius "$APP/.venv/bin/pip" install -q -r requirements.txt

sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now autoplius-ui.service
sudo systemctl restart autoplius-ui.service
sleep 2
sudo systemctl status autoplius-ui.service --no-pager || true

# open local firewall if ufw is active
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 8080/tcp || true
fi

curl -sS -o /dev/null -w "local_http=%{http_code}\n" http://127.0.0.1:8080/ || true
ss -lntp | grep 8080 || true
echo "UI should be at http://$(curl -s ifconfig.me 2>/dev/null || echo 62.84.122.165):8080"
