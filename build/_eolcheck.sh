#!/bin/bash
cd /mnt/d/Users/Documents/project/openwrt || exit 9
for f in build/build.sh build/setup-wsl.sh scripts/configure-newifi-router.sh; do
  if bash -n "$f" 2>/tmp/err; then
    echo "OK   $f"
  else
    echo "FAIL $f -> $(cat /tmp/err | head -1)"
  fi
  if tr -d '\r' < "$f" | bash -n 2>/dev/null; then
    echo "     stripped-CRLF: OK"
  else
    echo "     stripped-CRLF: FAIL"
  fi
done
