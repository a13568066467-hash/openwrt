#!/usr/bin/env python3
"""Deploy light-theme status page + updated nds-agent cloud.uc."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "openwrt-feed/nds-hooks/files/usr/lib/nds-hooks/client_status.sh"
AGENT = ROOT / "openwrt-feed/nds-agent/files/usr/lib/nds-agent/cloud.uc"
HOSTS = (
    os.environ.get("NDS_ROUTER_HOST", "192.168.1.1"),
    "192.168.10.1",
)
PASSWORD = os.environ.get("NDS_ROUTER_PASS", "1234567890")


def upload(client: paramiko.SSHClient, local: Path, remote: str, mode: int = 0o755) -> None:
    text = local.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    stdin, stdout, stderr = client.exec_command(
        f"mkdir -p $(dirname {remote}) && cat > {remote}", timeout=30
    )
    stdin.write(text)
    stdin.channel.shutdown_write()
    _ = stdout.read()
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("UPLOAD ERR", remote, err[-400:])
    client.exec_command(f"chmod {mode:o} {remote}", timeout=10)
    print("uploaded", remote, "bytes", len(text))


def main() -> None:
    last_err = None
    for host in HOSTS:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(
                host,
                username="root",
                password=PASSWORD,
                timeout=12,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            c.close()
            continue

        print("CONNECTED", host)
        upload(c, STATUS, "/usr/lib/nds-hooks/client_status.sh", 0o755)
        upload(c, AGENT, "/usr/lib/nds-agent/cloud.uc", 0o644)

        setup = r"""
set -e
uci set opennds.@opennds[0].gatewayname='NewWiFI'
uci set opennds.@opennds[0].gatewayfqdn='home.me'
uci set opennds.@opennds[0].statuspath='/usr/lib/nds-hooks/client_status.sh'
uci commit opennds
ip link set br-guest up 2>/dev/null || true
ifup guest 2>/dev/null || true
sleep 1
if ! ip -4 addr show br-guest | grep -q 192.168.100.1; then
  ip addr add 192.168.100.1/24 dev br-guest 2>/dev/null || true
  ip link set br-guest up
fi
/etc/init.d/nds-agent restart
/etc/init.d/opennds restart
sleep 12
echo === verify ===
uci -q get opennds.@opennds[0].gatewayfqdn
uci -q get opennds.@opennds[0].statuspath
head -2 /usr/lib/nds-hooks/client_status.sh
pidof opennds >/dev/null && echo opennds=UP || echo opennds=DOWN
pgrep -f nds-agent >/dev/null && echo agent=UP || echo agent=DOWN
ndsctl status 2>&1 | grep -E 'Gateway Name|Gateway FQDN|Managed' | head -6
"""
        _, stdout, stderr = c.exec_command(setup, timeout=90)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR", err[-1200:])
        c.close()
        return

    raise SystemExit(f"unreachable: {last_err}")


if __name__ == "__main__":
    main()
