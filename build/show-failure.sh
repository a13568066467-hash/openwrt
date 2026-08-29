#!/bin/bash
# Show the real failure in an OpenWrt package build log.
#   build/show-failure.sh <target>-<package>
LOG="/mnt/d/Users/Documents/project/openwrt/build/logs/${1:-x86_64-nds-profile}.log"

if [ ! -f "$LOG" ]; then
  echo "no such log: $LOG"
  ls /mnt/d/Users/Documents/project/openwrt/build/logs/
  exit 1
fi

echo "=== log: $LOG ($(wc -l < "$LOG") lines) ==="
echo
echo "=== 'failed to build' markers ==="
grep -n 'failed to build' "$LOG" | tail -10
echo
echo "=== make error exits ==="
grep -nE '^make(\[[0-9]+\])?: \*\*\*' "$LOG" | tail -15
echo
echo "=== first compiler/linker error ==="
grep -nE '(^|/)[A-Za-z0-9_.-]+:[0-9]+:[0-9]+: error:|No such file or directory|command not found|Permission denied' "$LOG" \
  | grep -v "s|@''" | head -15
echo
echo "=== last 40 lines ==="
tail -40 "$LOG" | cut -c1-200
