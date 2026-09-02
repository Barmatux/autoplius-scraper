#!/usr/bin/env bash
# Deploy autoplius-scraper on VM from git (source of truth).
# Triggered by GitHub Actions on push to main, or manually on VM:
#   sudo bash /opt/autoplius-scraper/deploy/deploy-from-git.sh
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
if [[ "${SKIP_GIT_PULL:-}" == "1" ]]; then
  echo "=== skip git pull (code synced by CI) ==="
else
  sudo -u autoplius git fetch "$REMOTE" "$BRANCH"

  # deploy/*.sh line-ending normalization can leave harmless local diffs; reset before pull.
  if sudo -u autoplius git status --porcelain deploy/ | grep -q .; then
    if sudo -u autoplius git diff -- deploy/ | grep -q .; then
      echo "=== reset deploy/ content drift ==="
      sudo -u autoplius git checkout -- deploy/
    fi
    chmod +x "$APP"/deploy/*.sh
  fi

  if sudo -u autoplius git status --porcelain | grep -q .; then
    echo "=== stash leftover VM changes (tracked + untracked) ==="
    sudo -u autoplius git stash push -u -m "deploy-autostash-$(date +%Y%m%d-%H%M%S)" || true
  fi

  if sudo -u autoplius git status --porcelain | grep -q .; then
    echo "ERROR: VM working tree is still dirty after stash" >&2
    sudo -u autoplius git status -sb >&2 || true
    exit 1
  fi

  echo "=== pull --ff-only $REMOTE/$BRANCH ==="
  sudo -u autoplius git pull --ff-only "$REMOTE" "$BRANCH"
fi

echo "=== pip install ==="
sudo -u autoplius "$PIP" install -q -r requirements.txt

echo "=== normalize deploy scripts (LF + executable) ==="
for f in "$APP"/deploy/*.sh; do
  sed -i 's/\r$//' "$f"
  chmod +x "$f"
done
# Do not git checkout deploy/ here: that resets the +x bit and breaks systemd ExecStart.

echo "=== systemd units ==="
sudo cp "$APP/deploy/autoplius-scraper.service" "$APP/deploy/autoplius-scraper.timer" /etc/systemd/system/
sudo cp "$APP/deploy/autoplius-ui.service" /etc/systemd/system/
if [[ -f "$APP/deploy/autoplius-target-resume.service" ]]; then
  sudo cp "$APP/deploy/autoplius-target-resume.service" "$APP/deploy/autoplius-target-resume.timer" /etc/systemd/system/
fi
sudo systemctl daemon-reload
sudo systemctl enable autoplius-scraper.timer autoplius-ui.service

if [[ -f "$APP/deploy/post-deploy-vm.sh" ]]; then
  echo "=== post-deploy ==="
  bash "$APP/deploy/post-deploy-vm.sh"
fi

echo "=== restart UI ==="
sudo systemctl restart autoplius-ui.service
sleep 1
sudo systemctl is-active autoplius-ui.service
curl -s -o /dev/null -w "ui_http=%{http_code}\n" http://127.0.0.1:8080/ || true

REV="$(sudo -u autoplius git rev-parse --short HEAD)"
echo "=== deployed $REV ($BRANCH) ==="
