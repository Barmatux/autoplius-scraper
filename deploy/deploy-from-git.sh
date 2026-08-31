#!/usr/bin/env bash
# Deploy autoplius-scraper on VM from git (source of truth).
# Usage on VM: sudo bash /opt/autoplius-scraper/deploy/deploy-from-git.sh
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
REMOTE="${DEPLOY_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"
PY="$APP/.venv/bin/python"
PIP="$APP/.venv/bin/pip"

if [[ ! -d "$APP/.git" ]]; then
  echo "ERROR: $APP is not a git checkout" >&2
  exit 1
fi

cd "$APP"

echo "=== fetch $REMOTE/$BRANCH ==="
sudo -u autoplius git fetch "$REMOTE" "$BRANCH"

if sudo -u autoplius git status --porcelain | grep -q .; then
  echo "WARNING: working tree has local changes; pull may fail." >&2
  sudo -u autoplius git status -sb >&2
fi

echo "=== pull --ff-only $REMOTE/$BRANCH ==="
sudo -u autoplius git pull --ff-only "$REMOTE" "$BRANCH"

echo "=== pip install ==="
sudo -u autoplius "$PIP" install -q -r requirements.txt

echo "=== normalize deploy scripts (LF) ==="
for f in "$APP"/deploy/*.sh; do
  sed -i 's/\r$//' "$f"
  sudo chmod +x "$f"
done

echo "=== systemd units ==="
sudo cp "$APP/deploy/autoplius-scraper.service" "$APP/deploy/autoplius-scraper.timer" /etc/systemd/system/
sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable autoplius-scraper.timer autoplius-ui.service

echo "=== restart UI ==="
sudo systemctl restart autoplius-ui.service
sleep 1
sudo systemctl is-active autoplius-ui.service
curl -s -o /dev/null -w "ui_http=%{http_code}\n" http://127.0.0.1:8080/ || true

REV="$(sudo -u autoplius git rev-parse --short HEAD)"
echo "=== deployed $REV ($BRANCH) ==="
