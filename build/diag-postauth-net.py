#!/usr/bin/env python3
"""Diagnose guest → FAS path after home.me continue-login."""
from __future__ import annotations

import paramiko
import os

HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
PASS = os.environ["NDS_ROUTER_PASSWORD"]

CMD = r"""
set +e
echo '=== opennds key uci ==='
uci show opennds | grep -E 'fas|walled|gateway|secure|enabled|path'
echo
echo '=== firewall cloud rule ==='
uci show firewall | grep -E 'allow_cloud|guest_to|guest_portal|guest='
echo
echo '=== ndsctl status head ==='
ndsctl status 2>/dev/null | head -40
echo
echo '=== ndsctl clients ==='
ndsctl clients 2>/dev/null | head -80
echo
echo '=== json clients snippet ==='
ndsctl json 2>/dev/null | head -c 3500; echo
echo
echo '=== ip addrs ==='
ip -4 addr show br-guest; ip -4 addr show br-lan
echo
echo '=== from router to cloud ==='
curl -s -o /dev/null -w 'fas=%{http_code}\n' --connect-timeout 3 http://192.168.1.125:8080/fas
curl -s -o /dev/null -w 'portal=%{http_code}\n' --connect-timeout 3 http://192.168.1.125:8080/portal/
echo
echo '=== nft mention 192.168.1.125 / 8080 ==='
nft list ruleset 2>/dev/null | grep -n '192.168.1.125\|8080\|nds_\|opennds' | head -50
echo
echo '=== wifi guest iface ==='
iwinfo 2>/dev/null | head -40
echo
echo '=== dhcp leases guest ==='
cat /tmp/dhcp.leases 2>/dev/null
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    _, o, e = c.exec_command(CMD, timeout=90)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:\n", err[:800])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
