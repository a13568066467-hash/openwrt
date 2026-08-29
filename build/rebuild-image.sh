#!/bin/bash
# Incremental image rebuild with a PATH safe for OpenWrt's find -execdir.
set -euo pipefail
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/[a-z]/' | paste -sd:)"
export PATH
OWRT="${HOME}/owrt/openwrt"
cd "$OWRT"
make -j"$(nproc)" "$@"
echo "REBUILD_DONE"
