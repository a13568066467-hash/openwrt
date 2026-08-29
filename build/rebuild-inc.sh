#!/bin/bash
# Incremental rebuild: only nds-profile changed, reuse cached toolchain/kernel.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

OWRT="$HOME/owrt/openwrt"
PROJECT="/mnt/d/Users/Documents/project/openwrt"
cd "$OWRT"

./scripts/feeds update ndsbilling
make defconfig
make package/nds-profile/clean
make package/nds-profile/compile V=s -j4

echo "=== kernel (ensure up to date) ==="
make target/linux/compile -j4 V=s || make target/linux/compile -j1 V=s

echo "=== image ==="
if make -j8 > "$PROJECT/build/logs/x86_64-inc.log" 2>&1; then
  ls -lh bin/targets/x86/64/*.img.gz | tail -3
  echo "BUILD_COMPLETE"
else
  tail -25 "$PROJECT/build/logs/x86_64-inc.log"
  echo "BUILD_FAILED"
  exit 1
fi
