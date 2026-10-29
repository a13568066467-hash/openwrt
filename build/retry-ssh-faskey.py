#!/usr/bin/env python3
"""Retry LAN-bound SSH until faskey is synced."""
from __future__ import annotations

import socket
import time
import os

import paramiko

HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
PASS = os.environ["NDS_ROUTER_PASSWORD"]
FAS_KEY = os.environ["NDS_FAS_KEY"]
CLOUD = os.environ.get("NDS_CLOUD_HOST", "192.168.1.125")

CMD = f"""
uci set opennds.@opennds[0].faskey='{FAS_KEY}'
uci set opennds.@opennds[0].fasremoteip='{CLOUD}'
uci commit opennds
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
/etc/init.d/opennds restart
sleep 2
echo KEY=$(uci -q get opennds.@opennds[0].faskey)
ndsctl status 2>/dev/null | grep -E 'FAS:|Gateway Name|Managed'
"""


def try_once() -> str:
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
    _, o, e = c.exec_command(CMD, timeout=90)
    out = o.read().decode() + e.read().decode()
    c.close()
    return out


def main() -> int:
    for i in range(12):
        try:
            print(f"attempt {i+1}")
            out = try_once()
            print(out)
            if f"KEY={FAS_KEY}" in out:
                print("SYNC_OK")
                return 0
            print("key mismatch or incomplete")
        except Exception as ex:
            print(f"fail: {ex}")
        time.sleep(2)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
