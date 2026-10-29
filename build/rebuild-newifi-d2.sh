#!/bin/bash
# Rebuild Newifi D2 (ramips/mt7621) firmware with current nds-billing feed.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

PROJECT="/mnt/d/Users/Documents/project/openwrt"
OWRT="/home/ubuntu/owrt/openwrt"
LOG="${PROJECT}/build/last-build-ramips_mt7621.log"
IMG="${PROJECT}/build/images"

mkdir -p "${PROJECT}/build/logs" "${IMG}"
cd "${OWRT}"

ln -sfn "${PROJECT}/openwrt-feed" feeds/nds-billing
./scripts/feeds update nds-billing || true
./scripts/feeds install -a -p nds-billing 2>/dev/null \
  || ./scripts/feeds install -p nds-billing opennds nds-agent nds-hooks nds-profile || true

cp "${PROJECT}/build/configs/ramips_mt7621.config" .config
make defconfig

make package/nds-hooks/clean package/nds-profile/clean package/nds-agent/clean || true

echo "BUILD_START=$(date -Iseconds)" | tee "${LOG}"
make -j"$(nproc)" V=s 2>&1 | tee -a "${LOG}"
echo "BUILD_END=$(date -Iseconds)" | tee -a "${LOG}"

echo "==> images"
ls -lh bin/targets/ramips/mt7621/*newifi-d2*.bin
echo "==> packages in manifest"
grep -E 'nds-|opennds' bin/targets/ramips/mt7621/*.manifest | head -30 || true

cp -v bin/targets/ramips/mt7621/openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin "${IMG}/"
cp -v bin/targets/ramips/mt7621/openwrt-ramips-mt7621-d-team_newifi-d2-initramfs-kernel.bin "${IMG}/"
cp -v bin/targets/ramips/mt7621/*.manifest "${IMG}/" 2>/dev/null || true

echo "BUILD_COMPLETE"
