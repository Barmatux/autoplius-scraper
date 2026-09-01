#!/usr/bin/env bash
# Keep a stable VM ui/app.py outside git (admin, catalog, all Jinja filters).
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
CANONICAL="${VM_UI_APP:-/var/lib/autoplius-scraper/vm-ui-app.py}"

if [[ -f "$CANONICAL" ]]; then
  echo "=== use VM ui/app.py from $CANONICAL ==="
  cp -a "$CANONICAL" "$APP/ui/app.py"
  exit 0
fi

if [[ -f /tmp/stashed_app.py ]]; then
  echo "=== seed VM ui/app.py from /tmp/stashed_app.py ==="
  mkdir -p "$(dirname "$CANONICAL")"
  cp -a /tmp/stashed_app.py "$CANONICAL"
  cp -a "$CANONICAL" "$APP/ui/app.py"
  exit 0
fi

echo "WARN: no VM ui/app.py baseline at $CANONICAL" >&2
exit 0
