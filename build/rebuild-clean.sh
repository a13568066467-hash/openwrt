#!/bin/bash
# Clean rebuild after tmp/ corruption. Single make session, no nested invocations.
set -euo pipefail

PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/[a-z]/' | paste -sd:)"
export PATH

OWRT="$HOME/owrt/openwrt"
PROJECT="/mnt/d/Users/Documents/project/openwrt"
FEED=ndsbilling
LOGDIR="$PROJECT/build/logs"

cd "$OWRT"
rm -rf tmp
grep -q "src-link $FEED " feeds.conf || echo "src-link $FEED $PROJECT/openwrt-feed" >> feeds.conf

./scripts/feeds update "$FEED"
./scripts/feeds install opennds
./scripts/feeds install -p "$FEED" nds-agent nds-hooks nds-profile

cp "$PROJECT/build/configs/x86_64.config" .config
make defconfig

echo "=== full image build ==="
if make -j8 > "$LOGDIR/x86_64-full.log" 2>&1; then
  find bin/targets -name '*.img.gz' -printf '  %p\n' | sed "s#$OWRT/##"
  echo "BUILD_COMPLETE"
else
  tail -30 "$LOGDIR/x86_64-full.log"
  echo "BUILD_FAILED"
  exit 1
fi
