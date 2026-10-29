#!/usr/bin/env python3
"""Make PC (192.168.1.125) the lab uplink for OpenWrt guest traffic."""
from __future__ import annotations

import socket
import time

import paramiko

HOST, LOCAL, PASS = "192.168.1.1", "192.168.1.125", "1234567890"

CMD = r"""
set -e
# Default route via lab PC
ip route replace default via 192.168.1.125 dev br-lan
# Persist lightly via hotplug-less: write to /etc/rc.local snippet if missing
grep -q '192.168.1.125' /etc/rc.local 2>/dev/null || {
  sed -i '/^exit 0/d' /etc/rc.local 2>/dev/null || true
  cat >> /etc/rc.local <<'EOF'
# lab uplink via PC when WAN has no carrier
ip route replace default via 192.168.1.125 dev br-lan 2>/dev/null || true
exit 0
EOF
  chmod +x /etc/rc.local
}

# Forward guest -> lan (PC gateway path)
uci -q delete firewall.guest_to_lan
uci set firewall.guest_to_lan=forwarding
uci set firewall.guest_to_lan.src='guest'
uci set firewall.guest_to_lan.dest='lan'

# Masquerade guest traffic leaving toward LAN/PC
uci -q delete firewall.guest_masq_lan
uci set firewall.guest_masq_lan=nat
uci set firewall.guest_masq_lan.name='Masq-Guest-to-LAN'
uci set firewall.guest_masq_lan.src='guest'
uci set firewall.guest_masq_lan.dest='lan'
uci set firewall.guest_masq_lan.target='MASQUERADE'
uci set firewall.guest_masq_lan.family='ipv4'

# Ensure lan zone can forward
uci set firewall.@zone[0].forward='ACCEPT' 2>/dev/null || true
# Find lan zone and enable masq as backup for outbound via br-lan
for s in $(uci show firewall | sed -n "s/^firewall\.\\([^=]*\\)=zone$/\\1/p"); do
  name=$(uci -q get firewall.$s.name)
  if [ "$name" = "lan" ]; then
    uci set firewall.$s.masq='1'
    uci set firewall.$s.mtu_fix='1'
  fi
done

uci commit firewall
/etc/init.d/firewall restart
sleep 2
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
# opennds may need restart after fw
/etc/init.d/opennds restart 2>/dev/null || true
sleep 3

echo '## routes'
ip route show default
echo '## ping via pc'
ping -c 2 -W 2 192.168.1.125 | tail -3
ping -c 2 -W 3 8.8.8.8 | tail -5
curl -s -o /dev/null -w 'baidu=%{http_code}\n' --connect-timeout 4 --max-time 6 http://www.baidu.com/ || echo baidu=FAIL
ndsctl status 2>/dev/null | grep -E 'Upstream|FAS:|Managed' | head -5
"""


def ssh(cmd: str, timeout: int = 120) -> str:
    last = None
    for _ in range(10):
        try:
            sock = socket.create_connection((HOST, 22), timeout=8, source_address=(LOCAL, 0))
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                HOST,
                username="root",
                password=PASS,
                sock=sock,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
            _, o, e = c.exec_command(cmd, timeout=timeout)
            out = o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")
            c.close()
            return out
        except Exception as ex:
            last = ex
            time.sleep(1.5)
    raise RuntimeError(last)


if __name__ == "__main__":
    print(ssh(CMD))
