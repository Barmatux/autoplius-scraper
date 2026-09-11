#!/usr/bin/env bash
# Warm anonymous home + catalog HTML after UI restart or page-cache invalidate.
# Fills gunicorn page_cache (per-worker) and optionally nginx proxy_cache.
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
PY="${DEPLOY_PY:-$APP/.venv/bin/python}"
ORIGIN_BASE="${UI_PREWARM_BASE:-http://127.0.0.1:8080}"
NGINX_BASE="${UI_PREWARM_NGINX_BASE:-https://127.0.0.1}"
HOST_HEADER="${UI_PREWARM_HOST:-eu2.by}"
ROUNDS="${UI_PREWARM_ROUNDS:-2}"
TIMEOUT="${UI_PREWARM_TIMEOUT_SEC:-120}"
# Paths hit through nginx (in addition to Python origin prewarm).
NGINX_PATHS="${UI_PREWARM_NGINX_PATHS:-/ /catalog}"

cd "$APP"

echo "=== prewarm origin ($ORIGIN_BASE) ==="
UI_PREWARM_BASE="$ORIGIN_BASE" UI_PREWARM_ROUNDS="$ROUNDS" UI_PREWARM_TIMEOUT_SEC="$TIMEOUT" \
  "$PY" - <<'PY'
from ui.prewarm import prewarm_home

for row in prewarm_home():
    status = row.get("status") or row.get("error")
    print(f"  round={row.get('round')} ok={row.get('ok')} {row.get('url')} -> {status}")
PY

if command -v curl >/dev/null 2>&1; then
  echo "=== prewarm nginx ($NGINX_BASE Host=$HOST_HEADER) ==="
  for path in $NGINX_PATHS; do
    url="${NGINX_BASE}${path}"
    echo "  path=${path}"
    # Two GETs: first may MISS/EXPIRED; second should HIT if cache works.
    for i in 1 2; do
      curl -skS -o /dev/null -m "$TIMEOUT" \
        -H "Host: $HOST_HEADER" \
        -H "User-Agent: eu2-prewarm/1.0" \
        -w "    try${i}: code=%{http_code} ttfb=%{time_starttransfer}s\n" \
        "$url" || true
    done
  done
fi

echo "=== prewarm done ==="
