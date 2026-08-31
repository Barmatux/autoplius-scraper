#!/usr/bin/env bash
# Pause target scrape, raise delays, schedule enrich-only resume.
# Usage: sudo bash deploy/schedule-target-resume.sh [hours_from_now]
set -euo pipefail

APP="${APP_DIR:-/opt/autoplius-scraper}"
ENV_FILE="$APP/.env"
RESUME_IN_HOURS="${1:-4}"
LOG="$APP/logs/schedule-target-resume.log"

mkdir -p "$(dirname "$LOG")"

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG"
}

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

log "=== schedule target enrich-only resume in ${RESUME_IN_HOURS}h ==="

log "Stopping running target scrape (if any)"
pkill -f 'python run_target_scrape.py' || true
sleep 2

log "Pausing hourly scraper timer (conflicts on browser profile)"
systemctl stop autoplius-scraper.timer || true

log "Raising scrape delays to reduce Autoplius rate limits"
set_env DETAIL_DELAY_SEC 8
set_env PAGE_DELAY_SEC 5
set_env TARGET_DETAIL_DELAY_SEC 10
set_env TARGET_PAGE_DELAY_SEC 6
set_env SCRAPE_TIMEOUT_SEC 120
set_env TRANSLATE_DELAY_SEC 1

RESUME_AT="$(date -u -d "+${RESUME_IN_HOURS} hours" '+%Y-%m-%d %H:%M:%S')"
log "Resume scheduled at ${RESUME_AT} UTC"

TIMER_FILE="$APP/deploy/autoplius-target-resume.timer"
sed -i "s|^OnCalendar=.*|OnCalendar=${RESUME_AT} UTC|" "$TIMER_FILE"

cp "$APP/deploy/autoplius-target-resume.service" /etc/systemd/system/
cp "$TIMER_FILE" /etc/systemd/system/
chmod +x "$APP/deploy/run-target-scrape.sh"
systemctl daemon-reload
systemctl enable autoplius-target-resume.timer
systemctl restart autoplius-target-resume.timer

log "Timer status:"
systemctl list-timers autoplius-target-resume.timer --no-pager | tee -a "$LOG"

PENDING="$(sudo -u autoplius bash -lc "cd $APP && set -a && source .env && set +a && .venv/bin/python - <<'PY'
from scraper.config import Settings
from scraper.db import fetch_listings_pending_detail
s = Settings.from_env()
print(len(fetch_listings_pending_detail(s.db_path)))
PY
")"
log "Pending detail listings in DB: ${PENDING}"
log "Done. Hourly timer stays stopped until target resume finishes."
