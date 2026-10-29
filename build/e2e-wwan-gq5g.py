#!/usr/bin/env python3
"""Configure radio1 STA -> GQ_5G as real WAN uplink."""
from __future__ import annotations

import socket
import time

import paramiko

HOST, LOCAL, PASS = "192.168.1.1", "192.168.1.125", "1234567890"
SSID = "GQ_5G"
KEY = "yl1234567890"

CMD = rf"""
set -x
# disable default AP on radio1
uci set wireless.default_radio1.disabled='1'
uci set wireless.radio1.disabled='0'
# channel auto for STA
uci set wireless.radio1.channel='auto'
uci delete wireless.wwan 2>/dev/null || true
uci set wireless.wwan=wifi-iface
uci set wireless.wwan.device='radio1'
uci set wireless.wwan.mode='sta'
uci set wireless.wwan.network='wwan'
uci set wireless.wwan.ssid='{SSID}'
uci set wireless.wwan.encryption='psk2'
uci set wireless.wwan.key='{KEY}'

uci delete network.wwan 2>/dev/null || true
uci set network.wwan=interface
uci set network.wwan.proto='dhcp'
uci set network.wwan.metric='5'

# Put wwan into wan firewall zone
wan_zone=
for s in $(uci show firewall | sed -n "s/^firewall\\.\\([^=]*\\)=zone$/\\1/p"); do
  [ "$(uci -q get firewall.$s.name)" = "wan" ] && wan_zone=$s
done
if [ -n "$wan_zone" ]; then
  # reset network list then add wan + wwan
  uci -q delete firewall.$wan_zone.network
  uci add_list firewall.$wan_zone.network='wan'
  uci add_list firewall.$wan_zone.network='wwan'
  uci set firewall.$wan_zone.masq='1'
  uci set firewall.$wan_zone.mtu_fix='1'
fi

uci commit wireless
uci commit network
uci commit firewall

wifi reload
sleep 2
ifup wwan 2>/dev/null || true
/etc/init.d/network reload
sleep 8
wifi status | head -c 2000; echo
iwinfo | head -40
echo '## addrs'
ip -4 addr show | awk '/^[0-9]+:/{{iface=$2}} /inet /{{print iface,$2}}'
echo '## routes'
ip route
echo '## ping'
# prefer wwan default; keep PC as backup with higher metric
ip route replace default via 192.168.1.125 metric 100 2>/dev/null || true
ping -c 2 -W 3 8.8.8.8 | tail -5
curl -s -o /dev/null -w 'baidu=%{{http_code}}\n' --connect-timeout 5 --max-time 8 http://www.baidu.com/ || echo baidu=FAIL
ubus call network.interface.wwan status 2>/dev/null | jsonfilter -e '@.up' -e '@["ipv4-address"][0].address'
"""


def ssh(cmd: str, timeout: int = 180) -> str:
    last = None
    for _ in range(8):
        try:
            sock = socket.create_connection((HOST, 22), timeout=8, source_address=(LOCAL, 0))
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                HOST,
                username="root",
                password=PASS,
                sock=sock,
                timeout=20,
                banner_timeout=20,
                auth_timeout=20,
                allow_agent=False,
                look_for_keys=False,
            )
            _, o, e = c.exec_command(cmd, timeout=timeout)
            out = o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")
            c.close()
            return out
        except Exception as ex:
            last = ex
            time.sleep(2)
    raise RuntimeError(last)


if __name__ == "__main__":
    print(ssh(CMD))
