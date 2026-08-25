FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install-deps chrome \
    && playwright install chrome

COPY . .

ENV TEST_MODE=true \
    SCRAPE_PAGES=10 \
    PAGE_DELAY_SEC=3 \
    AUTO_CAPTCHA=true \
    HEADLESS=true \
    DATA_DIR=/app/data \
    PROFILE_DIR=/app/.browser-profile \
    LOGS_DIR=/app/logs

CMD ["python", "scheduler.py"]
