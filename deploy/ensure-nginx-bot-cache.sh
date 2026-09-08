#!/usr/bin/env bash
# Install nginx shared page cache + safe AI-bot denylist (not Google/Yandex).
# Never replaces the whole site file (preserves Certbot SSL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZONE_SRC="$ROOT/deploy/nginx-conf.d/autoplius-cache.conf"
if [[ ! -f "$ZONE_SRC" && -f "$ROOT/deploy/nginx-conf.d/autoplius-bot-cache.conf" ]]; then
  ZONE_SRC="$ROOT/deploy/nginx-conf.d/autoplius-bot-cache.conf"
fi
SNIP_SRC="$ROOT/deploy/nginx-snippets/autoplius-proxy-cache.conf"
if [[ ! -f "$SNIP_SRC" ]]; then
  SNIP_SRC="$ROOT/deploy/nginx-snippets/autoplius-bot-proxy-cache.conf"
fi
LIMIT_SRC="$ROOT/deploy/nginx-conf.d/autoplius-bot-limit.conf"
MEDIA_SNIP_SRC="$ROOT/deploy/nginx-snippets/autoplius-bot-media.conf"
HTML_LIMIT_SRC="$ROOT/deploy/nginx-snippets/autoplius-bot-html-limit.conf"
ALLOW_SNIP_SRC="$ROOT/deploy/nginx-snippets/autoplius-bot-allowlist.conf"

ZONE_DST="/etc/nginx/conf.d/autoplius-cache.conf"
LIMIT_DST="/etc/nginx/conf.d/autoplius-bot-limit.conf"
SNIP_DST="/etc/nginx/snippets/autoplius-proxy-cache.conf"
MEDIA_SNIP_DST="/etc/nginx/snippets/autoplius-bot-media.conf"
HTML_LIMIT_DST="/etc/nginx/snippets/autoplius-bot-html-limit.conf"
ALLOW_SNIP_DST="/etc/nginx/snippets/autoplius-bot-allowlist.conf"
SITE="/etc/nginx/sites-available/autoplius-ui"
LOGROTATE_SRC="$ROOT/deploy/logrotate-autoplius.conf"

sudo mkdir -p /var/cache/nginx/autoplius /etc/nginx/snippets /etc/nginx/conf.d /var/log/autoplius-scraper
sudo cp "$ZONE_SRC" "$ZONE_DST"
sudo cp "$SNIP_SRC" "$SNIP_DST"
[[ -f "$LIMIT_SRC" ]] && sudo cp "$LIMIT_SRC" "$LIMIT_DST"
[[ -f "$MEDIA_SNIP_SRC" ]] && sudo cp "$MEDIA_SNIP_SRC" "$MEDIA_SNIP_DST"
[[ -f "$HTML_LIMIT_SRC" ]] && sudo cp "$HTML_LIMIT_SRC" "$HTML_LIMIT_DST"
[[ -f "$ALLOW_SNIP_SRC" ]] && sudo cp "$ALLOW_SNIP_SRC" "$ALLOW_SNIP_DST"
if [[ -f /etc/nginx/conf.d/autoplius-bot-cache.conf ]]; then
  sudo rm -f /etc/nginx/conf.d/autoplius-bot-cache.conf
fi
sudo chown -R www-data:www-data /var/cache/nginx/autoplius 2>/dev/null || sudo chown -R nginx:nginx /var/cache/nginx/autoplius 2>/dev/null || true
sudo touch /var/log/nginx/autoplius-timing.log
sudo chown www-data:adm /var/log/nginx/autoplius-timing.log 2>/dev/null || sudo chown nginx:root /var/log/nginx/autoplius-timing.log 2>/dev/null || true
sudo chown -R autoplius:autoplius /var/log/autoplius-scraper

if [[ -f "$LOGROTATE_SRC" ]]; then
  sudo cp "$LOGROTATE_SRC" /etc/logrotate.d/autoplius
fi

if [[ ! -f "$SITE" ]]; then
  echo "No $SITE — skip site inject"
  exit 0
fi

sudo python3 - <<'PY'
from pathlib import Path

site = Path("/etc/nginx/sites-available/autoplius-ui")
text = site.read_text(encoding="utf-8")
changed = False

if "snippets/autoplius-bot-proxy-cache.conf" in text:
    text = text.replace(
        "snippets/autoplius-bot-proxy-cache.conf",
        "snippets/autoplius-proxy-cache.conf",
    )
    changed = True

lines = text.splitlines(keepends=True)
out: list[str] = []
injected_allow = 0
injected_media = 0
injected_html = 0
injected_cache = 0
i = 0
while i < len(lines):
    line = lines[i]
    if line.strip() == "location / {":
        indent = line[: len(line) - len(line.lstrip())]
        lookback = "".join(out[-20:])
        if "autoplius-bot-allowlist.conf" not in lookback:
            out.append(f"{indent}include snippets/autoplius-bot-allowlist.conf;\n")
            injected_allow += 1
            changed = True
        if "autoplius-bot-media.conf" not in lookback and "location /media/" not in lookback:
            out.append(f"{indent}include snippets/autoplius-bot-media.conf;\n")
            injected_media += 1
            changed = True
        out.append(line)
        window = "".join(lines[i : i + 12])
        indent_inner = indent + "    "
        if "autoplius-bot-html-limit.conf" not in window:
            out.append(f"{indent_inner}include snippets/autoplius-bot-html-limit.conf;\n")
            injected_html += 1
            changed = True
        if "autoplius-proxy-cache.conf" not in window and "autoplius-bot-proxy-cache.conf" not in window:
            out.append(f"{indent_inner}include snippets/autoplius-proxy-cache.conf;\n")
            injected_cache += 1
            changed = True
        i += 1
        continue
    out.append(line)
    i += 1

text = "".join(out)

timing = "access_log /var/log/nginx/autoplius-timing.log autoplius_timing;"
if timing not in text:
    needle = "server_name eu2.by www.eu2.by"
    idx = text.find(needle)
    if idx != -1:
        server_pos = text.rfind("server {", 0, idx)
        if server_pos != -1:
            open_brace = text.find("{", server_pos)
            insert_at = text.find("\n", open_brace) + 1
            text = text[:insert_at] + "    " + timing + "\n" + text[insert_at:]
            changed = True
            print("injected autoplius-timing access_log")
else:
    print("timing access_log already present")

print(f"injected allowlist include: {injected_allow}")
print(f"injected media include: {injected_media}")
print(f"injected html-deny include: {injected_html}")
print(f"injected proxy-cache include: {injected_cache}")

if changed:
    site.write_text(text, encoding="utf-8")
    print("updated", site)
else:
    print("site already up to date")
PY

if sudo nginx -t; then
  sudo systemctl reload nginx
  echo "nginx reloaded with page cache + safe AI bot deny"
else
  echo "WARNING: nginx -t failed after bot-limit install — check sites-available/autoplius-ui"
  exit 1
fi
