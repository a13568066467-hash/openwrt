#!/bin/bash
# Static checks for the router-side shell scripts.
FEED=/mnt/d/Users/Documents/project/openwrt/openwrt-feed
FAIL=0

check() {
  local f="$1"
  printf '  %-24s ' "$(basename "$f")"
  if [ ! -f "$f" ]; then echo "MISSING"; FAIL=1; return; fi

  # uci-defaults and binauth run under busybox ash, so check with dash too.
  if ! sh -n "$f" 2>/tmp/sh.err; then
    echo "SYNTAX_FAIL"; sed 's/^/      /' /tmp/sh.err; FAIL=1; return
  fi
  if command -v dash >/dev/null 2>&1 && ! dash -n "$f" 2>/tmp/sh.err; then
    echo "DASH_FAIL"; sed 's/^/      /' /tmp/sh.err; FAIL=1; return
  fi
  if grep -q $'\r' "$f"; then
    echo "HAS_CRLF"; FAIL=1; return
  fi
  echo "OK"
}

echo "=== shell script checks ==="
check "$FEED/nds-hooks/files/usr/lib/nds-hooks/binauth.sh"
check "$FEED/nds-profile/files/etc/uci-defaults/99-nds-profile"
check "$FEED/nds-profile/files/etc/init.d/nds-late"
check "$FEED/nds-agent/files/etc/init.d/nds-agent"

printf '  %-24s ' "ieee80211 detection"
PROFILE="$FEED/nds-profile/files/etc/uci-defaults/99-nds-profile"
if grep -q 'ieee80211.*head -1' "$PROFILE"; then
  echo "FAIL (pipes ls through head)"
  FAIL=1
elif grep -q 'ls /sys/class/ieee80211/\*/ >/dev/null 2>&1' "$PROFILE"; then
  echo "OK"
else
  echo "FAIL (missing safe ieee80211 check)"
  FAIL=1
fi

echo
echo "=== binauth behaviour ==="
HOOK="$FEED/nds-hooks/files/usr/lib/nds-hooks/binauth.sh"
TMP=$(mktemp -d)
cp "$HOOK" "$TMP/hook.sh"; chmod +x "$TMP/hook.sh"
sed -i 's#/tmp/nds-events.jsonl#'"$TMP"'/events.jsonl#' "$TMP/hook.sh"

# Stand in for jsonfilter, which only exists on the router.
cat > "$TMP/jsonfilter" <<'STUB'
#!/bin/bash
field="${2#@.}"
python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$field',''))" 2>/dev/null
STUB
chmod +x "$TMP/jsonfilter"
export PATH="$TMP:$PATH"

CUSTOM=$(printf '%s' '{"user_id":7,"sessiontimeout":0,"upload_rate":2048,"download_rate":8192,"upload_quota":51200,"download_quota":51200}' | base64 -w0)

expect() {
  local label="$1" want="$2" got="$3"
  printf '  %-46s ' "$label"
  if [ "$got" = "$want" ]; then echo "PASS"; else echo "FAIL (got '$got', want '$want')"; FAIL=1; fi
}

out=$("$TMP/hook.sh" auth_client aa:bb:cc:dd:ee:ff 0 0 1700000000 0 tok "$CUSTOM")
expect "auth_client echoes the five quota parameters" "0 2048 8192 51200 51200" "$out"

out=$("$TMP/hook.sh" client_deauth aa:bb:cc:dd:ee:ff 100 200 1700000000 1700000100 tok "$CUSTOM")
expect "deauth notification produces no output" "" "$out"

out=$("$TMP/hook.sh" auth_client aa:bb:cc:dd:ee:ff 0 0 1700000000 0 tok "")
expect "missing custom data falls back to zeros" "0 0 0 0 0" "$out"

out=$("$TMP/hook.sh" auth_client aa:bb:cc:dd:ee:ff 0 0 1700000000 0 tok "!!!not-base64!!!")
expect "corrupt custom data falls back to zeros" "0 0 0 0 0" "$out"

INJECT=$(printf '%s' '{"upload_rate":"0; touch /tmp/pwned","download_rate":1}' | base64 -w0)
out=$("$TMP/hook.sh" auth_client aa:bb:cc:dd:ee:ff 0 0 1700000000 0 tok "$INJECT")
expect "non-numeric field is rejected, not evaluated" "0 0 1 0 0" "$out"
if [ -f /tmp/pwned ]; then echo "  FAIL: shell injection through custom data"; rm -f /tmp/pwned; FAIL=1; fi

"$TMP/hook.sh" client_auth aa:bb:cc:dd:ee:ff 1 2 3 4 tok "$CUSTOM" > /dev/null
lines=$(wc -l < "$TMP/events.jsonl")
printf '  %-46s ' "events are appended as one JSON line each"
[ "$lines" -ge 5 ] && echo "PASS ($lines lines)" || { echo "FAIL ($lines lines)"; FAIL=1; }

printf '  %-46s ' "each event line is valid JSON"
if python3 -c "
import json,sys
for line in open('$TMP/events.jsonl'):
    if line.strip(): json.loads(line)
" 2>/dev/null; then echo "PASS"; else echo "FAIL"; FAIL=1; fi

rm -rf "$TMP"
echo
[ "$FAIL" = 0 ] && echo "SHELL_TESTS_PASSED" || echo "SHELL_TESTS_FAILED"
exit $FAIL
