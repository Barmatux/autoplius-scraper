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

# Schema / SQL performance (each script is idempotent)
run_patch deploy/fix-db-engine-liters.py
run_patch deploy/patch-pagination.py
run_patch deploy/patch-sql-filters.py
run_patch deploy/patch-sql-filter-options.py
run_patch deploy/fix-sql-options-reuse.py
run_patch deploy/fix-tab-counts-sql.py

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
