#!/bin/bash
# Verify that a built image really contains the NDS billing stack.
# Mounts the ext4 rootfs offline, so it needs root:
#   wsl.exe -d Ubuntu-22.04 -u root -- bash build/verify-image.sh
set -u

OWRT="/home/ubuntu/owrt/openwrt"
IMG_GZ="$OWRT/bin/targets/x86/64/openwrt-x86-64-generic-ext4-rootfs.img.gz"
WORK=/tmp/nds-verify
MNT="$WORK/mnt"
FAIL=0

[ -f "$IMG_GZ" ] || { echo "image not found: $IMG_GZ"; exit 1; }

rm -rf "$WORK"; mkdir -p "$MNT"
gunzip -c "$IMG_GZ" > "$WORK/rootfs.img"
mount -o loop,ro "$WORK/rootfs.img" "$MNT" || { echo "mount failed"; exit 1; }

present() {
  local path="$1"
  printf '  %-46s ' "$path"
  if [ -e "$MNT$path" ]; then echo "OK"; else echo "MISSING"; FAIL=1; fi
}

contains() {
  local path="$1" needle="$2" label="$3"
  printf '  %-46s ' "$label"
  if [ -f "$MNT$path" ] && grep -qF "$needle" "$MNT$path"; then
    echo "OK"
  else
    echo "NOT FOUND"; FAIL=1
  fi
}

echo "=== agent files ==="
present /usr/lib/nds-agent/main.uc
present /usr/lib/nds-agent/quota.uc
present /usr/lib/nds-agent/cloud.uc
present /usr/lib/nds-agent/http.uc
present /usr/lib/nds-agent/ndsctl.uc
present /etc/config/nds-agent
present /etc/init.d/nds-agent

echo
echo "=== hook and profile ==="
present /usr/lib/nds-hooks/binauth.sh
present /etc/uci-defaults/99-nds-profile

echo
echo "=== runtime dependencies ==="
present /usr/bin/ucode
present /usr/lib/ucode/fs.so
present /usr/lib/ucode/uci.so
present /usr/bin/curl
present /usr/bin/ndsctl
present /usr/bin/opennds
present /usr/sbin/dnsmasq
present /usr/bin/jsonfilter

echo
echo "=== service autostart ==="
present /etc/rc.d/S99nds-agent
printf '  %-46s ' "opennds is enabled at boot"
if ls "$MNT"/etc/rc.d/S*opennds >/dev/null 2>&1; then
  echo "OK ($(basename "$(ls "$MNT"/etc/rc.d/S*opennds | head -1)"))"
else
  echo "MISSING"; FAIL=1
fi
echo "  --- all enabled services ---"
ls "$MNT/etc/rc.d/" | sort | sed 's/^/      /'

echo
echo "=== configuration content ==="
contains /etc/init.d/nds-agent "ucode -R /usr/lib/nds-agent/main.uc" "init runs ucode in raw mode"
contains /etc/uci-defaults/99-nds-profile "/usr/lib/nds-hooks/binauth.sh" "profile points binauth at our hook"
contains /etc/uci-defaults/99-nds-profile "fas_secure_enabled='4'" "openNDS configured for FAS level 4"
contains /etc/uci-defaults/99-nds-profile "Allow-DHCP-Guest" "guest zone permits DHCP"
contains /etc/uci-defaults/99-nds-profile "Allow-DNS-Guest" "guest zone permits DNS"
contains /etc/uci-defaults/99-nds-profile "ra='disabled'" "guest IPv6 router advertisements off"
contains /etc/config/nds-agent "backlog_file" "agent config has the backlog path"

echo
echo "=== dnsmasq variant (nftset support is required) ==="
printf '  %-46s ' "dnsmasq supports nftset"
if "$MNT/usr/sbin/dnsmasq" --version 2>/dev/null | grep -q nftset ||
   strings "$MNT/usr/sbin/dnsmasq" 2>/dev/null | grep -q nftset; then
  echo "OK"
else
  echo "NOT FOUND (walled garden will not work)"; FAIL=1
fi

echo
echo "=== image sizes ==="
ls -1 "$OWRT/bin/targets/x86/64/"*.img.gz 2>/dev/null | while read -r f; do
  printf '  %-56s %s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
done

umount "$MNT"
rm -rf "$WORK"

echo
[ "$FAIL" = 0 ] && echo "IMAGE_VERIFIED" || echo "IMAGE_VERIFICATION_FAILED"
exit $FAIL
