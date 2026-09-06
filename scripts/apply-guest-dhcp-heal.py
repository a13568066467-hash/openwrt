#!/usr/bin/env python3
"""Deploy guest-DHCP self-heal scripts to a live Newifi lab router (SSH, no SFTP)."""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "openwrt-feed" / "nds-profile" / "files"

FILES = {
    "/usr/lib/nds-profile/ensure-guest-dhcp.sh": PROFILE
    / "usr/lib/nds-profile/ensure-guest-dhcp.sh",
    "/etc/init.d/nds-late": PROFILE / "etc/init.d/nds-late",
    "/etc/hotplug.d/iface/99-nds-guest-dhcp": PROFILE
    / "etc/hotplug.d/iface/99-nds-guest-dhcp",
    "/etc/hotplug.d/net/99-nds-guest-dhcp": PROFILE
    / "etc/hotplug.d/net/99-nds-guest-dhcp",
}

HOSTS = [
    os.environ.get("NDS_ROUTER_HOST", "192.168.10.1"),
    "192.168.1.1",
]
USER = os.environ.get("NDS_ROUTER_USER", "root")
PASSWORD = os.environ.get("NDS_ROUTER_PASS", "1234567890")


def b64_file(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return base64.b64encode(data).decode("ascii")


def build_remote() -> str:
    parts = [
        "set -e",
        "mkdir -p /usr/lib/nds-profile /etc/hotplug.d/iface /etc/hotplug.d/net /etc/init.d",
    ]
    for remote, local in FILES.items():
        parts.append(f"echo '{b64_file(local)}' | base64 -d > '{remote}'")
        parts.append(f"chmod +x '{remote}'")

    parts.extend(
        [
            "uci set dhcp.guest.force='1'",
            "uci set dhcp.guest.ignore='0'",
            "uci set dhcp.guest.dhcpv4='server'",
            "uci commit dhcp",
            "/etc/init.d/nds-late enable",
            "/etc/init.d/nds-late restart",
            "sleep 2",
            "/usr/lib/nds-profile/ensure-guest-dhcp.sh",
            "echo DEPLOY_OK",
        ]
    )
    return "\n".join(parts)


def main() -> int:
    remote = build_remote()
    last_err = None
    for host in HOSTS:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host,
                username=USER,
                password=PASSWORD,
                timeout=6,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            client.close()
            continue

        print(f"deploying to {host} ...")
        _, stdout, stderr = client.exec_command(remote, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        client.close()
        print(out)
        if err.strip():
            print(err, file=sys.stderr)
        return code

    print(f"unreachable: {last_err}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
