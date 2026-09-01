#!/bin/bash
# Run cloud API in WSL so QEMU guest can reach it at 10.0.2.2 (slirp gateway).
set -euo pipefail

PROJECT="/mnt/d/Users/Documents/project/openwrt"
CLOUD="$PROJECT/cloud"
WIN_HOST="$(grep -m1 nameserver /etc/resolv.conf | awk '{print $2}')"
PID_FILE="/tmp/nds-cloud-e2e.pid"
LOG_FILE="$PROJECT/build/logs/e2e-cloud.log"

mkdir -p "$PROJECT/build/logs" "$CLOUD/data"

if [ ! -f "$CLOUD/data/dev.crt" ] || [ ! -f "$CLOUD/data/dev.key" ]; then
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$CLOUD/data/dev.key" -out "$CLOUD/data/dev.crt" -days 365 -nodes \
    -subj "/CN=portal.local" \
    -addext "subjectAltName=DNS:portal.local,DNS:localhost,IP:10.0.2.2,IP:127.0.0.1" \
    2>/dev/null || openssl req -x509 -newkey rsa:2048 \
    -keyout "$CLOUD/data/dev.key" -out "$CLOUD/data/dev.crt" -days 365 -nodes \
    -subj "/CN=portal.local"
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "cloud already running (pid $(cat "$PID_FILE"))"
  exit 0
fi

export HTTP_PORT=8080
export HTTPS_PORT=8443
export TLS_CERT="$CLOUD/data/dev.crt"
export TLS_KEY="$CLOUD/data/dev.key"
export DATABASE_DSN="nds:nds123@tcp(${WIN_HOST}:3307)/nds_billing?charset=utf8mb4&parseTime=True&loc=Local"
export REDIS_ADDR="${WIN_HOST}:6380"
export JWT_SECRET=dev-jwt-secret-change-in-production
export FAS_KEY=nds-billing-fas-key
export AUTH_LOG_PATH="$CLOUD/data/auth_queue"
export QUOTA_EXPIRY_DAYS=90

cd "$CLOUD"
nohup go run ./cmd/server > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "E2E_CLOUD_STARTED pid=$(cat "$PID_FILE") win_host=$WIN_HOST"
  echo "  HTTP  :8080  HTTPS :8443 (WSL, reachable from QEMU at 10.0.2.2)"
else
  echo "E2E_CLOUD_FAILED"; tail -20 "$LOG_FILE"; exit 1
fi
