#!/bin/bash
set -euo pipefail
PROJECT="/mnt/d/Users/Documents/project/openwrt"
OWRT="$HOME/owrt/openwrt"

ln -sf "$PROJECT/openwrt-feed" "$OWRT/feeds/nds-billing"
cd "$OWRT"
./scripts/feeds update nds-billing 2>/dev/null || true
./scripts/feeds install -p nds-billing opennds nds-agent nds-hooks nds-profile

cp "$PROJECT/build/configs/x86_64.config" .config
make defconfig

echo "=== Building NDS packages ==="
make -j$(nproc) package/opennds/compile V=s
make -j$(nproc) package/nds-hooks/compile V=s
make -j$(nproc) package/nds-agent/compile V=s
make -j$(nproc) package/nds-profile/compile V=s

echo "=== Building x86_64 firmware ==="
make -j$(nproc) V=s 2>&1 | tee "$PROJECT/build/last-build-x86_64.log" | tail -50

echo "BUILD_COMPLETE"
