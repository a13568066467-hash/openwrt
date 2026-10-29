#!/usr/bin/env python3
"""Verify opennds up + FAS login success returns opennds_auth redirect."""
from __future__ import annotations

import re
import socket
import time
import urllib.parse
import urllib.request
import os

import paramiko

HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
PASS = os.environ["NDS_ROUTER_PASSWORD"]


def ssh(cmd: str) -> str:
    for _ in range(6):
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
            _, o, e = c.exec_command(cmd, timeout=60)
            out = o.read().decode() + e.read().decode()
            c.close()
            return out
        except Exception as ex:
            print("ssh retry", ex)
            time.sleep(2)
    raise RuntimeError("ssh failed")


def main() -> None:
    print("=== router ===")
    print(
        ssh(
            """
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
sleep 1
echo KEY=$(uci -q get opennds.@opennds[0].faskey | head -c 20)...
ndsctl status 2>/dev/null | sed -n '1,22p'
ip -4 addr show br-guest | awk '/inet /{print}'
"""
        )
    )

    # Get a fresh fas from opennds by simulating - or use a minimal crafted one
    # Use last known fas structure with current hid from a live client if any
    print("=== check portal config ===")
    with urllib.request.urlopen("http://127.0.0.1:8080/health") as r:
        print("health", r.read())

    # Login with known user - need live fas with hid from phone.
    # Probe: ask opennds for client list
    print(ssh("ndsctl json 2>/dev/null | head -c 800; echo"))


if __name__ == "__main__":
    main()
