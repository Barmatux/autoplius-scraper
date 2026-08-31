#!/usr/bin/env bash
set -euo pipefail

APP=/opt/autoplius-scraper
ENV_FILE="$APP/.env"
COMPOSE_FILE="$APP/deploy/docker-compose.minio.yml"

echo "=== MinIO for autoplius-scraper ==="

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy from .env.example first"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
S3_BUCKET="${S3_BUCKET:-autoplius-media}"

grep -q '^MINIO_ROOT_USER=' "$ENV_FILE" || echo "MINIO_ROOT_USER=$MINIO_ROOT_USER" | sudo tee -a "$ENV_FILE"
grep -q '^MINIO_ROOT_PASSWORD=' "$ENV_FILE" || echo "MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD" | sudo tee -a "$ENV_FILE"
grep -q '^S3_ENDPOINT_URL=' "$ENV_FILE" || echo "S3_ENDPOINT_URL=http://127.0.0.1:9000" | sudo tee -a "$ENV_FILE"
grep -q '^S3_ACCESS_KEY=' "$ENV_FILE" || echo "S3_ACCESS_KEY=$MINIO_ROOT_USER" | sudo tee -a "$ENV_FILE"
grep -q '^S3_SECRET_KEY=' "$ENV_FILE" || echo "S3_SECRET_KEY=$MINIO_ROOT_PASSWORD" | sudo tee -a "$ENV_FILE"
grep -q '^S3_BUCKET=' "$ENV_FILE" || echo "S3_BUCKET=$S3_BUCKET" | sudo tee -a "$ENV_FILE"
grep -q '^S3_REGION=' "$ENV_FILE" || echo "S3_REGION=us-east-1" | sudo tee -a "$ENV_FILE"

echo "=== Start MinIO container ==="
cd "$APP"
sudo docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

echo "=== Wait for MinIO ==="
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:9000/minio/health/live" >/dev/null 2>&1; then
    echo "MinIO is up"
    break
  fi
  echo "Waiting... ($attempt/10)"
  sleep 2
  if [ "$attempt" -eq 10 ]; then
    echo "MinIO health check failed"
    sudo docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=50
    exit 1
  fi
done

echo "=== Ensure bucket via Python ==="
sudo -u autoplius "$APP/.venv/bin/pip" install -q boto3
sudo -u autoplius bash -c "cd $APP && set -a && source .env && set +a && $APP/.venv/bin/python - <<'PY'
from scraper.config import Settings
from scraper.s3_storage import ensure_bucket_exists, get_s3_client
settings = Settings.from_env()
ensure_bucket_exists(settings)
client = get_s3_client(settings)
client.head_bucket(Bucket=settings.s3_bucket)
print('bucket ok:', settings.s3_bucket)
PY"

echo "=== Restart UI (media proxy) ==="
sudo systemctl restart autoplius-ui.service || true

echo "MinIO console: http://127.0.0.1:9001 (SSH tunnel only)"
echo "S3 API: http://127.0.0.1:9000"
echo "Next: bash $APP/deploy/sync-photos.sh"
