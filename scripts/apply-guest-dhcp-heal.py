#!/usr/bin/env python3
"""Deploy guest-DHCP self-heal scripts to a live Newifi lab router (SSH stdin, no SFTP/base64)."""
from __future__ import annotations

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
    os.environ.get("NDS_ROUTER_HOST", "192.168.1.1"),
    "192.168.10.1",
]
USER = os.environ.get("NDS_ROUTER_USER", "root")
PASSWORD = os.environ.get("NDS_ROUTER_PASS") or os.environ.get("NDS_ROUTER_PASSWORD", "1234567890")


def upload(client: paramiko.SSHClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    stdin, stdout, stderr = client.exec_command(
        f"mkdir -p $(dirname '{remote}') && cat > '{remote}' && chmod +x '{remote}'",
        timeout=60,
    )
    stdin.write(data)
    stdin.channel.shutdown_write()
    _ = stdout.read()
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        raise RuntimeError(f"upload {remote}: {err}")
    print(f"uploaded {remote} ({len(data)} bytes)")


def main() -> int:
    last_err = None
    for host in HOSTS:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host,
                username=USER,
                password=PASSWORD,
                timeout=8,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            client.close()
            continue

        print(f"deploying to {host} ...")
        for remote, local in FILES.items():
            upload(client, local, remote)

        setup = r"""
set -e
uci set dhcp.guest.force='1'
uci set dhcp.guest.ignore='0'
uci set dhcp.guest.dhcpv4='server'
uci commit dhcp
/etc/init.d/nds-late enable
/etc/init.d/nds-late restart
sleep 2
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
echo DEPLOY_OK
"""
        _, stdout, stderr = client.exec_command(setup, timeout=120)
        print(stdout.read().decode("utf-8", "replace"))
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        client.close()
        if err.strip():
            print(err, file=sys.stderr)
        return code

    print(f"unreachable: {last_err}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
