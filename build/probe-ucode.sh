#!/bin/bash
UCODE_BUILD="$HOME/ucode-src/build"
UCODE="$UCODE_BUILD/ucode"

echo "=== is raw mode the default in the pinned build? ==="
printf 'print("RAW_MODE_DEFAULT");\n' > /tmp/mode.uc
echo -n "  no flag : "; "$UCODE" -L "$UCODE_BUILD" /tmp/mode.uc 2>&1; echo
echo -n "  with -R : "; "$UCODE" -L "$UCODE_BUILD" -R /tmp/mode.uc 2>&1; echo

echo
echo "=== main.uc end-to-end run (stubbed ndsctl/curl/uci) ==="
LAB=/tmp/nds-lab
if [ ! -d "$LAB" ]; then echo "run test-agent.sh first"; exit 1; fi
export PATH="$LAB/bin:$PATH"

# main.uc loops forever; run it briefly and confirm it starts and enforces.
timeout 12 "$UCODE" -L "$UCODE_BUILD" -L "$LAB" "$LAB/main.uc" 2>&1 | head -20
echo "  (exit after timeout is expected for a daemon)"
echo MAINTEST_DONE
