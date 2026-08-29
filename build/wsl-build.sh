#!/bin/bash
# Build the NDS billing firmware for one target.
#
#   ./wsl-build.sh [target] [--packages-only]
#
# Defaults to x86_64. Logs land in build/logs/.
set -euo pipefail

# WSL appends the Windows PATH, and entries containing spaces ("C:\Program
# Files\...") arrive split into relative fragments. GNU find refuses to run
# -execdir when PATH holds a relative entry, which breaks package/install near
# the very end of the build. Windows paths are of no use here anyway.
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/[a-z]/' | paste -sd:)"
export PATH

PROJECT="/mnt/d/Users/Documents/project/openwrt"
OWRT="$HOME/owrt/openwrt"
TARGET="${1:-x86_64}"
MODE="${2:-full}"
LOGDIR="$PROJECT/build/logs"
JOBS="$(nproc)"

CONFIG="$PROJECT/build/configs/$TARGET.config"
[ -f "$CONFIG" ] || { echo "no config for target '$TARGET'"; exit 1; }
[ -d "$OWRT" ] || { echo "OpenWrt tree missing at $OWRT"; exit 1; }

mkdir -p "$LOGDIR"

# scripts/feeds only accepts \w+ as a feed name, so no hyphen here.
FEED=ndsbilling

echo "=== [1/5] wiring the $FEED feed ==="
cd "$OWRT"
[ -f feeds.conf ] || cp feeds.conf.default feeds.conf
sed -i '/nds-billing/d' feeds.conf
rm -f feeds/nds-billing
grep -q "src-link $FEED " feeds.conf || echo "src-link $FEED $PROJECT/openwrt-feed" >> feeds.conf
./scripts/feeds update "$FEED"
# opennds comes from the routing feed; only our own packages are installed here.
./scripts/feeds install opennds
./scripts/feeds install -p "$FEED" nds-agent nds-hooks nds-profile

echo "=== [2/5] applying $TARGET config ==="
cp "$CONFIG" .config
make defconfig > /dev/null

echo "--- resolved selections ---"
grep -E '^CONFIG_PACKAGE_(opennds|nds-|curl|ucode|dnsmasq)' .config | sort

echo "=== [3/5] toolchain + kernel ==="
# Built separately so a failure here is not buried in package logs. The kernel
# is required before any package with a kmod dependency (nds-profile pulls in
# kmod-nft-core) can be compiled.
make -j"$JOBS" tools/install toolchain/install > "$LOGDIR/$TARGET-toolchain.log" 2>&1 || {
  echo "toolchain build FAILED, tail of log:"; tail -40 "$LOGDIR/$TARGET-toolchain.log"; exit 1; }

make -j"$JOBS" target/compile > "$LOGDIR/$TARGET-kernel.log" 2>&1 || {
  echo "kernel build FAILED, tail of log:"; tail -40 "$LOGDIR/$TARGET-kernel.log"; exit 1; }

echo "=== [4/5] nds packages ==="
for pkg in nds-hooks nds-agent nds-profile; do
  printf '  %-12s ' "$pkg"
  if make -j"$JOBS" "package/$pkg/compile" V=s > "$LOGDIR/$TARGET-$pkg.log" 2>&1; then
    echo OK
  else
    echo FAIL; tail -30 "$LOGDIR/$TARGET-$pkg.log"; exit 1
  fi
done

if [ "$MODE" = "--packages-only" ]; then
  echo "PACKAGES_COMPLETE"
  exit 0
fi

echo "=== [5/5] firmware image ==="
if make -j"$JOBS" > "$LOGDIR/$TARGET-image.log" 2>&1; then
  echo "--- images ---"
  find bin/targets -type f \( -name '*.img.gz' -o -name '*.bin' -o -name '*.img' \) \
    -printf '  %-70p %8s bytes\n' 2>/dev/null | sed "s#$OWRT/##"
  echo "BUILD_COMPLETE"
else
  echo "image build FAILED, tail of log:"
  tail -60 "$LOGDIR/$TARGET-image.log"
  exit 1
fi
