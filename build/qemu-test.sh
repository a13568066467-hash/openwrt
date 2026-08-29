#!/bin/bash
# Boot the built image under QEMU and check that the NDS stack comes up.
#
# Uses two NICs: eth0 stays on br-lan (OpenWrt default), eth1 is attached to
# br-guest by nds-profile on headless targets. Serial console only — no SSH.
set -u

OWRT="/home/ubuntu/owrt/openwrt"
IMG_GZ="$OWRT/bin/targets/x86/64/openwrt-x86-64-generic-ext4-combined.img.gz"
WORK=/tmp/nds-qemu
BOOT_SECONDS="${1:-120}"
FAIL=0

[ -f "$IMG_GZ" ] || { echo "image not found: $IMG_GZ"; exit 1; }
command -v qemu-system-x86_64 >/dev/null || { echo "qemu-system-x86_64 not installed"; exit 1; }

rm -rf "$WORK"; mkdir -p "$WORK"
gunzip -c "$IMG_GZ" > "$WORK/disk.img"
qemu-img resize -f raw "$WORK/disk.img" 512M >/dev/null 2>&1

cat > "$WORK/probe.sh" <<'PROBE'
echo "=====NDS_PROBE_BEGIN====="
echo "--openwrt--"; . /etc/openwrt_release 2>/dev/null; echo "$DISTRIB_RELEASE $DISTRIB_ARCH"
echo "--uci-defaults-left--"; ls /etc/uci-defaults/ 2>/dev/null | wc -l
echo "--opennds-start--"; grep '^START=' /etc/init.d/opennds
echo "--opennds-running--"; pgrep -x opennds >/dev/null && echo yes || echo no
echo "--agent-running--"; pgrep -f 'nds-agent/main.uc' >/dev/null && echo yes || echo no
echo "--guest-iface--"; ip -4 addr show br-guest 2>/dev/null | grep -c 'inet '
echo "--guest-ports--"; uci -q get network.guest_dev.ports 2>/dev/null || echo none
echo "--eth1-in-br--"; ip link show master br-guest 2>/dev/null | grep -c eth1 || echo 0
echo "--guest-ipv6--"; ip -6 addr show br-guest 2>/dev/null | grep -c 'scope global'
echo "--nds-fas-level--"; uci -q get opennds.@opennds[0].fas_secure_enabled
echo "--nds-binauth--"; uci -q get opennds.@opennds[0].binauth
echo "--fw-guest-rules--"; uci show firewall 2>/dev/null | grep -c 'Allow-.*-Guest'
echo "--agent-syntax--"; ucode -R -e 'import { report } from "/usr/lib/nds-agent/cloud.uc"; print(type(report));' 2>&1
echo "--opennds-log--"; logread 2>/dev/null | grep -i opennds | tail -3
echo "=====NDS_PROBE_END====="
PROBE

echo "=== booting (${BOOT_SECONDS}s, dual NIC) ==="
(
  sleep "$BOOT_SECONDS"
  printf '\n'
  sleep 2
  cat "$WORK/probe.sh"
  sleep 15
  printf '\npoweroff -f\n'
  sleep 5
) | timeout $((BOOT_SECONDS + 90)) qemu-system-x86_64 \
      -M pc -m 512 -smp 2 -nographic -no-reboot \
      -drive file="$WORK/disk.img",format=raw,if=ide \
      -netdev user,id=lan -device e1000,netdev=lan \
      -netdev user,id=guest -device e1000,netdev=guest \
      -serial mon:stdio > "$WORK/console.log" 2>&1

cp "$WORK/console.log" /mnt/d/Users/Documents/project/openwrt/build/logs/qemu-console.log 2>/dev/null || true

if ! grep -q 'NDS_PROBE_BEGIN' "$WORK/console.log"; then
  echo "probe never ran; last 30 lines:"
  tail -30 "$WORK/console.log"
  exit 1
fi

sed -n '/NDS_PROBE_BEGIN/,/NDS_PROBE_END/p' "$WORK/console.log" | sed 's/\r//g' > "$WORK/probe.out"

# Each marker is on its own line; the value is on the following line.
probe_val() {
  grep -A1 "^--$1--$" "$WORK/probe.out" 2>/dev/null | tail -1 \
    | sed 's/root@OpenWrt:~#.*//' | tr -d '\r' | xargs
}

expect() {
  local label="$1" want="$2" got="$3"
  printf '  %-44s ' "$label"
  if [ "$got" = "$want" ]; then echo "PASS"; else echo "FAIL (got '$got', want '$want')"; FAIL=1; fi
}

echo
echo "=== boot checks ==="
printf '  %-44s %s\n' "openwrt release" "$(probe_val openwrt)"
expect "first-boot uci-defaults consumed" "0" "$(probe_val uci-defaults-left)"
expect "opennds starts after network" "START=21" "$(probe_val opennds-start)"
expect "opennds process is running" "yes" "$(probe_val opennds-running)"
expect "nds-agent process is running" "yes" "$(probe_val agent-running)"
expect "guest bridge has an IPv4 address" "1" "$(probe_val guest-iface)"
expect "guest ports include eth1" "eth1" "$(probe_val guest-ports)"
expect "eth1 is attached to br-guest" "1" "$(probe_val eth1-in-br)"
expect "guest bridge has no global IPv6" "0" "$(probe_val guest-ipv6)"
expect "openNDS runs at FAS level 4" "4" "$(probe_val nds-fas-level)"
expect "binauth points at our hook" "/usr/lib/nds-hooks/binauth.sh" "$(probe_val nds-binauth)"
expect "guest firewall rules present" "3" "$(probe_val fw-guest-rules)"
expect "agent modules load on target" "function" "$(probe_val agent-syntax)"

echo
echo "opennds log (last lines):"
probe_val opennds-log | sed 's/^/    /'

echo
echo "console log: build/logs/qemu-console.log"
[ "$FAIL" = 0 ] && echo "QEMU_BOOT_VERIFIED" || echo "QEMU_BOOT_FAILED"
exit $FAIL
