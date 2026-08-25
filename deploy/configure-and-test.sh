#!/usr/bin/env bash
set -euo pipefail

APP=/opt/autoplius-scraper

# .env (key passed as first arg)
KEY="${1:?captcha key required}"
sudo -u autoplius tee "$APP/.env" >/dev/null <<EOF
TEST_MODE=true
SCRAPE_PAGES=10
PAGE_DELAY_SEC=3
SCRAPE_INTERVAL_HOURS=1
SCRAPE_TIMEOUT_SEC=180
AUTO_CAPTCHA=true
HEADLESS=true
CAPTCHA_2CAPTCHA_API_KEY=${KEY}
DATA_DIR=/var/lib/autoplius-scraper/data
PROFILE_DIR=/var/lib/autoplius-scraper/browser-profile
LOGS_DIR=/var/log/autoplius-scraper
EOF
sudo chmod 600 "$APP/.env"
sudo chown autoplius:autoplius "$APP/.env"

# systemd units from repo
sudo cp "$APP/deploy/autoplius-scraper.service" /etc/systemd/system/
sudo cp "$APP/deploy/autoplius-scraper.timer" /etc/systemd/system/
sudo chmod +x "$APP/deploy/run-scrape.sh"

# allow autoplius to read system chrome profile dirs if needed
sudo usermod -aG video autoplius || true

sudo systemctl daemon-reload
sudo systemctl enable --now autoplius-scraper.timer
sudo systemctl status autoplius-scraper.timer --no-pager || true
systemctl list-timers --all | grep autoplius || true

echo "=== smoke test (2 pages) ==="
sudo -u autoplius bash -lc "cd $APP && SCRAPE_PAGES=2 .venv/bin/python run_scrape.py --pages 2"
echo "=== last_run ==="
sudo cat /var/lib/autoplius-scraper/data/last_run.json || true
