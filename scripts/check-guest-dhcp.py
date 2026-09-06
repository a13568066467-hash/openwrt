#!/usr/bin/env python3
"""Red-capable probe: guest WiFi must auto-assign IPs (br-guest + dhcp-range)."""
from __future__ import annotations

import os
import sys

import paramiko

HOSTS = [
    os.environ.get("NDS_ROUTER_HOST", "192.168.10.1"),
    "192.168.1.1",
]
USER = os.environ.get("NDS_ROUTER_USER", "root")
PASSWORD = os.environ.get("NDS_ROUTER_PASS", "1234567890")

REMOTE = r"""
set +e
echo "=== guest dhcp probe ==="
br_ip=$(ip -4 addr show br-guest 2>/dev/null | awk '/inet /{print $2; exit}')
br_op=$(cat /sys/class/net/br-guest/operstate 2>/dev/null)
guest_up=$(ubus call network.interface.guest status 2>/dev/null | jsonfilter -e '@.up')
guest_err=$(ubus call network.interface.guest status 2>/dev/null | jsonfilter -e '@.errors[0].code')
range=$(grep -h 'dhcp-range=.*,192\.168\.100\.' /var/etc/dnsmasq.conf* 2>/dev/null | head -1)
force=$(uci -q get dhcp.guest.force)
ignore=$(uci -q get dhcp.guest.ignore)
dns_pid=$(pidof dnsmasq)

echo "br_ip=${br_ip:-NONE}"
echo "br_operstate=${br_op:-NONE}"
echo "guest_up=${guest_up:-NONE}"
echo "guest_err=${guest_err:-NONE}"
echo "dhcp_force=${force:-NONE}"
echo "dhcp_ignore=${ignore:-NONE}"
echo "dnsmasq_pid=${dns_pid:-NONE}"
echo "dhcp_range=${range:-NONE}"

ok=1
echo "$br_ip" | grep -q '192\.168\.100\.1' || ok=0
[ "$br_op" = "up" ] || ok=0
[ -n "$range" ] || ok=0
[ -n "$dns_pid" ] || ok=0
[ "$force" = "1" ] || echo "WARN: dhcp.guest.force is not 1 (recommended)"

if [ "$ok" = "1" ]; then
  echo "RESULT=PASS"
  exit 0
fi
echo "RESULT=FAIL"
exit 1
"""


def connect(host: str) -> paramiko.SSHClient | None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            host,
            username=USER,
            password=PASSWORD,
            timeout=6,
            banner_timeout=8,
            allow_agent=False,
            look_for_keys=False,
        )
        return client
    except Exception as exc:  # noqa: BLE001
        client.close()
        print(f"host={host} connect_failed={exc.__class__.__name__}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    last_err = "no hosts tried"
    for host in HOSTS:
        client = connect(host)
        if client is None:
            last_err = host
            continue

        _, stdout, stderr = client.exec_command(REMOTE, timeout=30)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        client.close()
        print(f"host={host}")
        print(out, end="")
        if err.strip():
            print(err, file=sys.stderr)
        return code

    print(f"RESULT=FAIL unreachable last={last_err}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
