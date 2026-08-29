#!/bin/bash
# Host-side validation of the nds-agent ucode modules.
#
# Stubs ndsctl and curl so the quota/reporting logic can be exercised without
# a router, then compiles and runs assertions against the real interpreter
# pinned to the same commit OpenWrt 25.12 ships.
set -u

UCODE_BUILD="$HOME/ucode-src/build"
UCODE="$UCODE_BUILD/ucode"
SRC="/mnt/d/Users/Documents/project/openwrt/openwrt-feed/nds-agent/files/usr/lib/nds-agent"
LAB=/tmp/nds-lab

if [ ! -x "$UCODE" ]; then echo "missing ucode at $UCODE"; exit 1; fi

rm -rf "$LAB"; mkdir -p "$LAB/bin" "$LAB/state"
cp "$SRC"/*.uc "$LAB"/
sed -i 's/\r$//' "$LAB"/*.uc

# --- stub: ndsctl -----------------------------------------------------------
cat > "$LAB/bin/ndsctl" <<'STUB'
#!/bin/bash
case "$1" in
  json)   cat /tmp/nds-lab/clients.json ;;
  deauth) echo "$2" >> /tmp/nds-lab/deauth.log; echo "Client $2 deauthenticated" ;;
  *)      echo "" ;;
esac
STUB

# --- stub: curl -------------------------------------------------------------
cat > "$LAB/bin/curl" <<'STUB'
#!/bin/bash
cp /tmp/nds-agent-request.json /tmp/nds-lab/last-request.json 2>/dev/null
cat /tmp/nds-lab/response.json
printf '\n<<<STATUS:200'
STUB

# --- stub: uci module (host ucode is built without UCI support) -------------
cat > "$LAB/uci.uc" <<'STUB'
function cursor() {
	return {
		load: function(p) { return true; },
		get: function(cfg, sec, opt) { return null; },
	};
}
export { cursor };
STUB

chmod +x "$LAB/bin/ndsctl" "$LAB/bin/curl"
export PATH="$LAB/bin:$PATH"

# ndsctl.uc hardcodes /usr/bin/ndsctl; point it at the stub for this run.
sed -i "s#const NDSCTL = '/usr/bin/ndsctl';#const NDSCTL = '$LAB/bin/ndsctl';#" "$LAB/ndsctl.uc"

# This ucode build has no `-c module` mode, so each module is loaded through a
# real import instead; that exercises the same parse path the router will use.
echo "=== 1. module load check ==="
FAIL=0
for m in ndsctl quota http cloud; do
  printf '  %-12s ' "$m.uc"
  echo "import * as m from './$m.uc'; print('loaded');" > "$LAB/load-$m.uc"
  if out=$("$UCODE" -L "$UCODE_BUILD" -L "$LAB" "$LAB/load-$m.uc" 2>&1); then
    echo OK
  else
    echo FAIL; echo "$out" | sed 's/^/      /' | head -10; FAIL=1
  fi
done
[ "$FAIL" = 1 ] && { echo "MODULE_LOAD_FAILED"; exit 1; }

# --- fixtures ---------------------------------------------------------------
# 1000 kB down + 500 kB up = 1500 kB = 1536000 bytes for the combined counter.
cat > "$LAB/clients.json" <<'JSON'
{
  "clients": {
    "aa:bb:cc:dd:ee:ff": {
      "mac": "AA:BB:CC:DD:EE:FF",
      "ip": "192.168.9.42",
      "token": "tok123",
      "state": "Authenticated",
      "session_start": 1700000000,
      "download_this_session": 1000,
      "upload_this_session": 500
    },
    "11:22:33:44:55:66": {
      "mac": "11:22:33:44:55:66",
      "ip": "192.168.9.43",
      "token": "tok456",
      "state": "Preauthenticated",
      "session_start": 0,
      "download_this_session": 0,
      "upload_this_session": 0
    }
  }
}
JSON

echo '{"ok":true,"quota_updates":[{"mac":"aa:bb:cc:dd:ee:ff","user_id":7,"remaining_bytes":900000}]}' > "$LAB/response.json"

echo
echo "=== 2. behavioural assertions ==="
cat > "$LAB/spec.uc" <<'SPEC'
import { snapshot, enforce, set_remaining, load, save, get } from './quota.uc';
import { report, load_seq, is_online } from './cloud.uc';
import { readfile } from 'fs';

let pass = 0, fail = 0;
function check(name, cond, detail) {
	if (cond) { pass++; printf('  PASS  %s\n', name); }
	else { fail++; printf('  FAIL  %s  (%s)\n', name, detail ?? ''); }
}

const MAC = 'aa:bb:cc:dd:ee:ff';
const SESSION_BYTES = 1536000;

let live = snapshot();
check('snapshot returns only authenticated clients', length(live) == 1, `got ${length(live)}`);
check('combined counter converts kB to bytes',
      live[0].total_bytes == SESSION_BYTES, `got ${live[0]?.total_bytes}`);
check('mac is normalised to lowercase', live[0].mac == MAC, live[0]?.mac);

check('no deauth when quota is unknown', length(enforce()) == 0);

set_remaining(MAC, 2000000, 7, 0);
check('client under quota stays authenticated', length(enforce()) == 0);

set_remaining(MAC, 1000000, 7, 0);
let expired = enforce();
check('client over combined quota is deauthenticated',
      length(expired) == 1 && expired[0].mac == MAC, `got ${length(expired)}`);

/* Offline credit: cloud says 900000 left having booked 500000 of the session. */
set_remaining(MAC, 900000, 7, 500000);
let after = snapshot();
check('baseline excludes bytes the cloud already booked',
      after[0].uncredited_bytes == SESSION_BYTES - 500000, `got ${after[0]?.uncredited_bytes}`);

let config = {
	device_id: 'router-1', device_secret: 's3cr3t',
	cloud_url: 'https://example.invalid', request_timeout: 5, insecure_tls: true,
	quota_file: '/tmp/nds-lab/state/quota.json',
	backlog_file: '/tmp/nds-lab/state/backlog.jsonl',
	seq_file: '/tmp/nds-lab/state/seq',
};

load_seq(config.seq_file);
let resp = report(config);
check('report succeeds against stubbed cloud', resp?.ok == true);
check('agent considers cloud online', is_online() == true);

let sent = json(readfile('/tmp/nds-lab/last-request.json'));
check('credentials travel in the JSON body, not headers',
      sent.device_id == 'router-1' && sent.device_secret == 's3cr3t');
check('exactly one delta report is sent', length(sent.reports) == 1, `got ${length(sent.reports)}`);
check('delta equals unreported bytes',
      sent.reports[0].delta_bytes == SESSION_BYTES, `got ${sent.reports[0]?.delta_bytes}`);
check('sequence number starts at 1', sent.reports[0].seq == 1, `got ${sent.reports[0]?.seq}`);
check('session_key is namespaced by device',
      index(sent.reports[0].session_key, 'router-1:') == 0, sent.reports[0]?.session_key);

check('cloud quota update is applied', get(MAC).remaining_bytes == 900000,
      `got ${get(MAC)?.remaining_bytes}`);
check('sequence counter is persisted', trim(readfile(config.seq_file)) == '1');

/* Second pass: nothing new was consumed, so no request should be issued. */
system('rm -f /tmp/nds-lab/last-request.json');
report(config);
check('no duplicate report when usage is unchanged',
      readfile('/tmp/nds-lab/last-request.json') == null);

save(config.quota_file);
check('quota cache persists as valid JSON',
      json(readfile(config.quota_file))[MAC].remaining_bytes == 900000);

printf('\n  %d passed, %d failed\n', pass, fail);
exit(fail > 0 ? 1 : 0);
SPEC

"$UCODE" -L "$UCODE_BUILD" -L "$LAB" "$LAB/spec.uc" 2>&1
RC=$?

echo
echo "=== 3. offline degradation ==="
cat > "$LAB/bin/curl" <<'STUB'
#!/bin/bash
exit 7
STUB
chmod +x "$LAB/bin/curl"
# uclient-fetch must also be absent for the fallback path to fail
cat > "$LAB/bin/uclient-fetch" <<'STUB'
#!/bin/bash
exit 4
STUB
chmod +x "$LAB/bin/uclient-fetch"

cat > "$LAB/offline.uc" <<'SPEC'
import { snapshot, set_remaining } from './quota.uc';
import { report, is_online, load_seq } from './cloud.uc';
import { readfile } from 'fs';

let pass = 0, fail = 0;
function check(name, cond, detail) {
	if (cond) { pass++; printf('  PASS  %s\n', name); }
	else { fail++; printf('  FAIL  %s  (%s)\n', name, detail ?? ''); }
}

let config = {
	device_id: 'router-1', device_secret: 's3cr3t',
	cloud_url: 'https://example.invalid', request_timeout: 2, insecure_tls: true,
	quota_file: '/tmp/nds-lab/state/quota.json',
	backlog_file: '/tmp/nds-lab/state/backlog-offline.jsonl',
	seq_file: '/tmp/nds-lab/state/seq-offline',
};

load_seq(config.seq_file);
snapshot();
let resp = report(config);
check('report returns null when cloud is unreachable', resp == null);
check('agent marks cloud offline', is_online() == false);

let backlog = readfile(config.backlog_file);
check('unsent report is buffered to disk', backlog != null && length(trim(backlog)) > 0);

let buffered = json(split(trim(backlog), '\n')[0]);
check('buffered entry keeps its sequence number', buffered.seq > 0, `got ${buffered?.seq}`);
check('buffered entry keeps the delta', buffered.delta_bytes == 1536000,
      `got ${buffered?.delta_bytes}`);

printf('\n  %d passed, %d failed\n', pass, fail);
exit(fail > 0 ? 1 : 0);
SPEC

"$UCODE" -L "$UCODE_BUILD" -L "$LAB" "$LAB/offline.uc" 2>&1
RC2=$?

echo
echo "=== deauth log ==="
cat "$LAB/deauth.log" 2>/dev/null || echo "(none)"

if [ "$RC" = 0 ] && [ "$RC2" = 0 ]; then echo "AGENT_TESTS_PASSED"; else echo "AGENT_TESTS_FAILED"; fi
