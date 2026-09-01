#!/bin/bash
set -euo pipefail
DEVICE_ID="${1:-NDS-Billing-Gateway}"
SECRET="${2:-nds-qemu-secret-16}"
curl -s -X POST "http://127.0.0.1:8080/api/v1/device/register" \
  -H 'Content-Type: application/json' \
  -d "{\"device_id\":\"$DEVICE_ID\",\"name\":\"QEMU E2E\",\"secret\":\"$SECRET\"}" \
  && echo REGISTER_OK || echo REGISTER_SKIP
