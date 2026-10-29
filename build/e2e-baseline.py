#!/usr/bin/env python3
"""E2E lab baseline probe (LAN-bound SSH)."""
from __future__ import annotations

import socket
import time
import urllib.request
import os

import paramiko

HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
PASS = os.environ["NDS_ROUTER_PASSWORD"]
FAS_KEY = os.environ["NDS_FAS_KEY"]

CMD = r"""
echo '## wan'
ubus call network.interface.wan status 2>/dev/null | jsonfilter -e 'up=@.up' -e 'ip=@["ipv4-address"][0].address' -e 'gw=@.route[0].nexthop' -e 'proto=@.proto'
ip -o link show wan 2>/dev/null | head -1
ip route show default 2>/dev/null | head -3
ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 && echo ping8=OK || echo ping8=FAIL
curl -s -o /dev/null -w 'curl_baidu=%{http_code}\n' --connect-timeout 3 --max-time 5 http://www.baidu.com/ || echo curl_baidu=FAIL

echo '## guest'
ip -4 addr show br-guest 2>/dev/null | awk '/inet /{print "br-guest="$2}'
cat /sys/class/net/br-guest/operstate 2>/dev/null
grep -E 'dhcp-range=set:guest' /var/etc/dnsmasq.conf.* 2>/dev/null | head -1
iwinfo 2>/dev/null | head -12

echo '## opennds'
uci -q get opennds.@opennds[0].faskey
uci -q get opennds.@opennds[0].fasremoteip
uci -q get opennds.@opennds[0].fas_secure_enabled
ndsctl status 2>/dev/null | sed -n '1,22p'

echo '## fw'
uci show firewall.guest_to_wan 2>/dev/null
uci show firewall.allow_cloud_guest 2>/dev/null
"""


def ssh(cmd: str, timeout: int = 60) -> str:
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


def main() -> None:
    print("=== cloud ===")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=3) as r:
            print("health", r.read().decode())
        with urllib.request.urlopen("http://192.168.1.125:8080/health", timeout=3) as r:
            print("lan health", r.read().decode())
    except Exception as e:
        print("cloud FAIL", e)

    print("=== router ===")
    out = ssh(CMD)
    print(out)
    key = None
    for line in out.splitlines():
        if line.startswith("d9e74f") or (len(line) == 64 and all(c in "0123456789abcdef" for c in line)):
            key = line.strip()
    if key == FAS_KEY:
        print("faskey=MATCH")
    else:
        print("faskey=MISMATCH want", FAS_KEY[:16], "got", (key or "?")[:16])


if __name__ == "__main__":
    main()
