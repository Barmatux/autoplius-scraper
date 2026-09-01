#!/bin/bash
set -euo pipefail
cd /opt/autoplius-scraper

TMP=/tmp/autoplius-merge-$$
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

git show 'stash@{0}:ui/app.py' > "$TMP/stashed_app.py"
git show 'stash@{0}:scraper/db.py' > "$TMP/stashed_db.py"
git show 'stash@{0}:ui/static/style.css' > "$TMP/stashed_style.css"
git show HEAD:ui/app.py > "$TMP/git_app.py"
git show HEAD:scraper/db.py > "$TMP/git_db.py"
git show HEAD:ui/static/style.css > "$TMP/git_style.css"

cp "$TMP/stashed_app.py" /tmp/stashed_app.py
cp "$TMP/stashed_db.py" /tmp/stashed_db.py
cp "$TMP/stashed_style.css" /tmp/stashed_style.css
cp "$TMP/git_app.py" /tmp/git_app.py
cp "$TMP/git_db.py" /tmp/git_db.py
cp "$TMP/git_style.css" /tmp/git_style.css

python3 deploy/merge-vm-app-admin.py
python3 deploy/merge-vm-db-admin.py
python3 deploy/merge-vm-style-css.py
python3 deploy/patch-vm-index-admin.py

echo "Merge complete"
