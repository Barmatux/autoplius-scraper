#!/usr/bin/env bash
set -euo pipefail
CANONICAL=/var/lib/autoplius-scraper/vm-ui-app.py
cp -a /tmp/stashed_app.py "$CANONICAL"
cp -a "$CANONICAL" /opt/autoplius-scraper/ui/app.py
echo "seeded $CANONICAL"
