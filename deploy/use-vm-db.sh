#!/usr/bin/env bash
set -euo pipefail
APP="${APP_DIR:-/opt/autoplius-scraper}"
CANONICAL="${VM_DB_PY:-/var/lib/autoplius-scraper/vm-db.py}"

if [[ -f "$CANONICAL" ]]; then
  echo "=== use VM scraper/db.py from $CANONICAL ==="
  cp -a "$CANONICAL" "$APP/scraper/db.py"
  exit 0
fi

cd "$APP"
if sudo -u autoplius git stash list | grep -q .; then
  echo "=== seed VM scraper/db.py from stash@{0} ==="
  sudo -u autoplius git checkout "stash@{0}" -- scraper/db.py
  mkdir -p "$(dirname "$CANONICAL")"
  cp -a "$APP/scraper/db.py" "$CANONICAL"
  exit 0
fi

echo "WARN: no VM scraper/db.py baseline at $CANONICAL" >&2
exit 0
