#!/bin/bash
# Recover from config/kernel drift: re-apply our minimal config, rebuild kernel
# cleanly, then repack the image.
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

OWRT="$HOME/owrt/openwrt"
PROJECT="/mnt/d/Users/Documents/project/openwrt"
cd "$OWRT"

cp "$PROJECT/build/configs/x86_64.config" .config
make defconfig

echo "=== clean kernel tree ==="
make target/linux/clean

echo "=== rebuild kernel ==="
make target/linux/compile -j4 V=s

echo "=== rebuild nds-profile ==="
./scripts/feeds update ndsbilling
make package/nds-profile/clean
make package/nds-profile/compile -j4 V=s

echo "=== pack image ==="
if make -j8 > "$PROJECT/build/logs/x86_64-recover.log" 2>&1; then
  ls -lh bin/targets/x86/64/openwrt-x86-64-generic-ext4-combined.img.gz
  echo "BUILD_COMPLETE"
else
  tail -30 "$PROJECT/build/logs/x86_64-recover.log"
  echo "BUILD_FAILED"
  exit 1
fi
