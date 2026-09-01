#!/usr/bin/env bash
set -euo pipefail
APP=/opt/autoplius-scraper
BK=/var/lib/autoplius-scraper/pre-deploy-backup.tgz
cd "$APP"

echo "=== snapshot ui/autoplius/scraper overlays ==="
tar czf "$BK" ui autoplius scraper/db.py scraper/job.py scraper/listing_sync.py deploy/nginx-autoplius-ui.conf

echo "=== stash ==="
sudo -u autoplius git stash push -u -m "deploy-manual-fix-$(date +%Y%m%d-%H%M%S)"

echo "=== pull ==="
sudo -u autoplius git pull --ff-only origin main

echo "=== restore overlay ==="
tar xzf "$BK" -C "$APP"

echo "=== post-deploy ==="
bash "$APP/deploy/post-deploy-vm.sh"

echo "=== restart UI ==="
systemctl restart autoplius-ui.service
sleep 2
curl -s -o /dev/null -w "ui_http=%{http_code} ttfb=%{time_starttransfer}s\n" http://127.0.0.1:8080/
sudo -u autoplius git rev-parse --short HEAD
