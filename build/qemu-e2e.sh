#!/bin/bash
# Fresh QEMU disk + auto-provision cloud URL for WSL-hosted API (10.0.2.2).
set -u

OWRT="/home/ubuntu/owrt/openwrt"
IMG_GZ="$OWRT/bin/targets/x86/64/openwrt-x86-64-generic-ext4-combined.img.gz"
WORK=/tmp/nds-qemu-interactive
BOOT_SECONDS="${1:-120}"
DEVICE_SECRET="${NDS_QEMU_SECRET:-nds-qemu-secret-16}"

[ -f "$IMG_GZ" ] || { echo "image not found: $IMG_GZ"; exit 1; }
command -v qemu-system-x86_64 >/dev/null || { echo "qemu-system-x86_64 not installed"; exit 1; }

rm -rf "$WORK"; mkdir -p "$WORK"
echo "Preparing fresh disk from image..."
gunzip -c "$IMG_GZ" > "$WORK/disk.img"
qemu-img resize -f raw "$WORK/disk.img" 512M >/dev/null 2>&1

cat > "$WORK/provision.sh" <<PROV
echo "=====NDS_E2E_PROVISION====="
if ! uci -q get network.guest_dev.ports 2>/dev/null | grep -q eth1; then
  uci add_list network.guest_dev.ports='eth1'
  uci commit network
  /etc/init.d/network reload
  sleep 5
fi
if ! ip link show br-guest >/dev/null 2>&1; then
  /etc/init.d/network reload
  sleep 3
fi
uci set opennds.@opennds[0].fasremotefqdn='10.0.2.2'
uci set opennds.@opennds[0].fasport='8443'
uci delete opennds.@opennds[0].walledgarden_fqdn_list
uci add_list opennds.@opennds[0].walledgarden_fqdn_list='10.0.2.2'
uci set nds-agent.main.cloud_url='https://10.0.2.2:8443'
uci set nds-agent.main.device_id='NDS-Billing-Gateway'
uci set nds-agent.main.device_secret='${DEVICE_SECRET}'
uci set nds-agent.main.insecure_tls='1'
uci commit opennds
uci commit nds-agent
/etc/init.d/opennds restart
/etc/init.d/nds-agent restart
sleep 5
echo "--br-guest--"; ip -4 addr show br-guest 2>/dev/null | grep inet || echo missing
echo "--guest-port--"; uci -q get network.guest_dev.ports || echo none
echo "--agent--"; pgrep -fa 'nds-agent/main.uc' || echo down
echo "--opennds--"; pgrep -x opennds && echo up || echo down
echo "--cloud-probe--"; curl -sk -o /dev/null -w '%{http_code}' https://10.0.2.2:8443/fas 2>/dev/null || echo fail
echo "=====NDS_E2E_READY====="
PROV

cat <<'HELP'
=== OpenWrt E2E (fresh boot + auto cloud config) ===
  Cloud API expected at https://10.0.2.2:8443 (WSL)
  Device ID: NDS-Billing-Gateway
  After boot, provisioning runs automatically (~120s).

  Quit: Ctrl+A then X
HELP

(
  sleep "$BOOT_SECONDS"
  printf '\n'
  sleep 2
  cat "$WORK/provision.sh"
  sleep 20
) | qemu-system-x86_64 \
  -M pc -m 512 -smp 2 -nographic -no-reboot \
  -drive file="$WORK/disk.img",format=raw,if=ide \
  -netdev user,id=lan -device e1000,netdev=lan \
  -netdev user,id=guest -device e1000,netdev=guest \
  -serial mon:stdio
