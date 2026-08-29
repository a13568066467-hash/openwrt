#!/bin/bash
# Validate nds-agent ucode scripts against a host-built ucode interpreter
set -u

UCODE_BUILD="$HOME/ucode-src/build"
UCODE="$UCODE_BUILD/ucode"
AGENT_DIR="/mnt/d/Users/Documents/project/openwrt/openwrt-feed/nds-agent/files/usr/lib/nds-agent"

if [ ! -x "$UCODE" ]; then
  echo "ucode binary not found at $UCODE"
  exit 1
fi

echo "=== fs module exports ==="
cat > /tmp/probe.uc <<'EOF'
import * as fs from 'fs';
let names = [];
for (let k in fs) push(names, k);
print('FS: ', join(' ', sort(names)), '\n');
print('builtins: system=', type(system), ' json=', type(json), ' time=', type(time),
      ' lc=', type(lc), ' sprintf=', type(sprintf), ' push=', type(push), '\n');
EOF
"$UCODE" -L "$UCODE_BUILD" /tmp/probe.uc
echo

echo "=== syntax check of agent modules ==="
STAGE=/tmp/nds-agent-stage
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$AGENT_DIR"/*.uc "$STAGE"/ 2>/dev/null
sed -i 's/\r$//' "$STAGE"/*.uc

for f in "$STAGE"/*.uc; do
  printf '%-40s ' "$(basename "$f")"
  # -c compiles without executing: pure syntax + import resolution check
  if "$UCODE" -L "$UCODE_BUILD" -c -o /dev/null "$f" 2>/tmp/err.txt; then
    echo "SYNTAX_OK"
  else
    echo "SYNTAX_FAIL"
    sed 's/^/    /' /tmp/err.txt | head -12
  fi
done

echo "VALIDATE_DONE"
