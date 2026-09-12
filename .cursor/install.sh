#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for autoplius-scraper.
# Creates a virtualenv, installs Python dependencies, and (best-effort) the
# Playwright browser used by the scraper. Safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

# Some default base images ship a python without the venv/ensurepip module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  pyver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  sudo apt-get update -qq
  sudo apt-get install -y -qq "python${pyver}-venv" || sudo apt-get install -y -qq python3-venv
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
# Test runner (repo uses a tests/ suite but does not pin pytest in requirements).
pip install pytest

# The scraper drives Playwright/Chromium. The Flask UI does not need a browser,
# so a failure here (e.g. missing system libs) must not break environment setup.
python -m playwright install chromium || echo "playwright browser install skipped (scraper-only dependency)"

echo "autoplius-scraper environment ready."
