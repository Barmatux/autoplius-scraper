#!/usr/bin/env bash
set -euo pipefail
cd /opt/autoplius-scraper
sudo -u autoplius git checkout stash@{0} -- scraper/db.py scraper/job.py scraper/listing_sync.py
sudo bash deploy/post-deploy-vm.sh
sudo systemctl restart autoplius-ui.service
sleep 2
curl -s -o /dev/null -w 'ui=%{http_code} ttfb=%{time_starttransfer}s\n' http://127.0.0.1:8080/
