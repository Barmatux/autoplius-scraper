#!/usr/bin/env bash
# Idempotent VM patches applied after git pull (safe to re-run on every deploy).
# Called from deploy-from-git.sh and GitHub Actions deploy workflow.
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
PY="${DEPLOY_PY:-$APP/.venv/bin/python}"

cd "$APP"

run_patch() {
  local script="$1"
  if [[ ! -f "$script" ]]; then
    echo "skip missing $script"
    return 0
  fi
  echo "=== $script ==="
  if sudo "$PY" "$script"; then
    echo "OK $script"
  else
    echo "WARN: $script exited $?" >&2
  fi
}

echo "=== post-deploy VM patches ==="

bash "$APP/deploy/use-vm-ui-app.sh"
bash "$APP/deploy/use-vm-db.sh"

if [[ -f "$APP/deploy/merge-vm-app-admin.py" ]]; then
  GIT_APP="/var/lib/autoplius-scraper/git_app.py"
  sudo bash -c "sudo -u autoplius git -C '$APP' show HEAD:ui/app.py > '$GIT_APP'"
  cp "$APP/ui/app.py" /tmp/stashed_app.py
  cp "$GIT_APP" /tmp/git_app.py
  chmod 644 "$GIT_APP" /tmp/git_app.py /tmp/stashed_app.py
  run_patch deploy/merge-vm-app-admin.py
fi
run_patch deploy/patch-vm-index-spec-context.py

# Schema / SQL performance (each script is idempotent)
run_patch deploy/fix-db-engine-liters.py
run_patch deploy/patch-pagination.py
run_patch deploy/patch-sql-filters.py
run_patch deploy/patch-sql-filter-options.py
run_patch deploy/fix-sql-options-reuse.py
run_patch deploy/fix-tab-counts-sql.py
run_patch deploy/fix-transmission-import.py
run_patch deploy/fix-vm-template-filters.py

# nginx: sync repo config when present (gzip may be enabled in sites-enabled separately)
if [[ -f deploy/nginx-autoplius-ui.conf ]]; then
  echo "=== nginx config ==="
  sudo cp deploy/nginx-autoplius-ui.conf /etc/nginx/sites-available/autoplius-ui
  sudo ln -sf /etc/nginx/sites-available/autoplius-ui /etc/nginx/sites-enabled/autoplius-ui
  if [[ -f deploy/fix-nginx-gzip.py ]]; then
    run_patch deploy/fix-nginx-gzip.py
  fi
  sudo nginx -t
  sudo systemctl reload nginx
fi

echo "=== post-deploy complete ==="
