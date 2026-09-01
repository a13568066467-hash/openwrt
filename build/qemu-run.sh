#!/bin/bash
# Interactive QEMU session for openwrt-feed acceptance testing.
#
#   wsl.exe -d Ubuntu-22.04 -- bash build/qemu-run.sh
#   powershell -File scripts/start-qemu.ps1
set -u

OWRT="/home/ubuntu/owrt/openwrt"
IMG_GZ="$OWRT/bin/targets/x86/64/openwrt-x86-64-generic-ext4-combined.img.gz"
WORK=/tmp/nds-qemu-interactive

[ -f "$IMG_GZ" ] || {
  echo "image not found: $IMG_GZ"
  echo "Build first: bash build/build.sh x86_64"
  exit 1
}
command -v qemu-system-x86_64 >/dev/null || {
  echo "qemu-system-x86_64 not installed — run: bash build/setup-wsl.sh"
  exit 1
}

mkdir -p "$WORK"
if [ ! -f "$WORK/disk.img" ]; then
  echo "Preparing disk image (first run may take ~30s)..."
  gunzip -c "$IMG_GZ" > "$WORK/disk.img"
  qemu-img resize -f raw "$WORK/disk.img" 512M
fi

cat <<'HELP'
=== OpenWrt QEMU (openwrt-feed) ===
  eth0 -> br-lan (LAN)
  eth1 -> br-guest (NDS guest WiFi, attached by nds-profile)

  Login: root (no password on first boot)

  Acceptance checks:
    pgrep -fa 'nds-agent|opennds'
    uci show opennds.@opennds[0]
    ip addr show br-guest
    ucode -R -e 'import { report } from "/usr/lib/nds-agent/cloud.uc"; print(type(report));'

  Quit QEMU: Ctrl+A then X
  Shutdown guest: poweroff -f

HELP

exec qemu-system-x86_64 \
  -M pc -m 512 -smp 2 -nographic -no-reboot \
  -drive file="$WORK/disk.img",format=raw,if=ide \
  -netdev user,id=lan -device e1000,netdev=lan \
  -netdev user,id=guest -device e1000,netdev=guest \
  -serial mon:stdio
