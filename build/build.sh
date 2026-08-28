#!/bin/bash
# Build OpenWrt firmware with custom nds-billing feed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OWRT_DIR="${HOME}/owrt/openwrt"
TARGET="${1:-x86_64}"
JOBS="${JOBS:-$(nproc)}"

if [ ! -d "${OWRT_DIR}/.git" ]; then
  echo "OpenWrt not found at ${OWRT_DIR}. Run build/setup-wsl.sh first."
  exit 1
fi

cd "${OWRT_DIR}"

# Link custom feed
FEED_LINK="${OWRT_DIR}/feeds/nds-billing"
if [ ! -L "${FEED_LINK}" ]; then
  ln -sf "${PROJECT_DIR}/openwrt-feed" "${FEED_LINK}"
fi

./scripts/feeds update nds-billing 2>/dev/null || true
./scripts/feeds install -a -p nds-billing 2>/dev/null || ./scripts/feeds install -p nds-billing opennds nds-agent nds-hooks nds-profile 2>/dev/null || true

CONFIG_FILE="${SCRIPT_DIR}/configs/${TARGET}.config"
if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Config not found: ${CONFIG_FILE}"
  exit 1
fi

cp "${CONFIG_FILE}" .config
make defconfig

echo "==> Building target ${TARGET} with ${JOBS} jobs..."
make -j"${JOBS}" V=s 2>&1 | tee "${PROJECT_DIR}/build/last-build-${TARGET}.log"

echo "==> Build complete. Images:"
find bin/targets -name "*.img*" -o -name "*.bin" 2>/dev/null | head -20
