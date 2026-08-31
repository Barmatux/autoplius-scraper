#!/usr/bin/env bash
# Pull latest main on VM and restart UI. Prefer: deploy/deploy-from-git.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec sudo bash "$SCRIPT_DIR/deploy-from-git.sh"
