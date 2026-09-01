#!/bin/bash
# Forward WSL :8443/:8080 so QEMU guest (10.0.2.2) reaches cloud on Windows host.
set -euo pipefail

WIN_HOST="$(grep -m1 nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}')"
[ -n "$WIN_HOST" ] || WIN_HOST="$(ip route show default 2>/dev/null | awk '{print $3}')"
[ -n "$WIN_HOST" ] || { echo "cannot detect Windows host IP"; exit 1; }

command -v socat >/dev/null || {
  echo "socat missing; run: wsl -u root apt-get install -y socat"
  exit 1
}

pkill -9 -f 'socat TCP-LISTEN:8443' 2>/dev/null || true
pkill -9 -f 'socat TCP-LISTEN:8080' 2>/dev/null || true
sleep 1

nohup socat TCP-LISTEN:8443,bind=0.0.0.0,fork,reuseaddr TCP:"${WIN_HOST}":8443 >/tmp/nds-bridge-8443.log 2>&1 &
nohup socat TCP-LISTEN:8080,bind=0.0.0.0,fork,reuseaddr TCP:"${WIN_HOST}":8080 >/tmp/nds-bridge-8080.log 2>&1 &
sleep 1
echo "CLOUD_BRIDGE_STARTED win_host=$WIN_HOST"
