#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "=== swap ==="
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
free -h

echo "=== packages ==="
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3-venv python3-pip git curl ca-certificates \
  fonts-liberation libasound2t64 libatk-bridge2.0-0 libatk1.0-0 \
  libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 \
  libxcomposite1 libxdamage1 libxrandr2 xdg-utils wget unzip

echo "=== chrome ==="
if ! command -v google-chrome >/dev/null 2>&1 && ! command -v google-chrome-stable >/dev/null 2>&1; then
  wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt-get install -y -qq /tmp/chrome.deb || sudo apt-get -f install -y -qq
  rm -f /tmp/chrome.deb
fi
google-chrome --version 2>/dev/null || google-chrome-stable --version

echo "=== user/dirs ==="
if ! id autoplius >/dev/null 2>&1; then
  sudo useradd -r -m -d /var/lib/autoplius-scraper -s /bin/bash autoplius
fi
sudo mkdir -p /opt/autoplius-scraper /var/lib/autoplius-scraper/data /var/lib/autoplius-scraper/browser-profile /var/log/autoplius-scraper

echo "=== clone ==="
if [ ! -d /opt/autoplius-scraper/.git ]; then
  sudo rm -rf /opt/autoplius-scraper
  sudo git clone https://github.com/Barmatux/autoplius-scraper.git /opt/autoplius-scraper
else
  sudo git -C /opt/autoplius-scraper pull --ff-only || true
fi

echo "=== venv ==="
cd /opt/autoplius-scraper
if [ ! -d .venv ]; then
  sudo python3 -m venv .venv
fi
sudo /opt/autoplius-scraper/.venv/bin/pip install -q --upgrade pip
sudo /opt/autoplius-scraper/.venv/bin/pip install -q -r requirements.txt

echo "=== ownership ==="
sudo chown -R autoplius:autoplius /opt/autoplius-scraper /var/lib/autoplius-scraper /var/log/autoplius-scraper

echo "=== stage1 done ==="
df -h /
free -h
id autoplius
ls -la /opt/autoplius-scraper | head
