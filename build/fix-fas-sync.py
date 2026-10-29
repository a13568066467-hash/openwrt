#!/usr/bin/env python3
"""Sync FAS key + portal URL; register NewWiFI; restart cloud (LAN-bound SSH)."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(r"d:\Users\Documents\project\openwrt")
HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
PASS = os.environ["NDS_ROUTER_PASSWORD"]
CLOUD = os.environ.get("NDS_CLOUD_HOST", "192.168.1.125")
FAS_KEY = os.environ["NDS_FAS_KEY"]
DEVICE_ID = os.environ.get("NDS_DEVICE_ID", "NewWiFI")
SECRET = os.environ["NDS_DEVICE_SECRET"]


def ssh(cmd: str, timeout: int = 120) -> str:
    sock = socket.create_connection((HOST, 22), timeout=12, source_address=(LOCAL, 0))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
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
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    client.close()
    return out + (("\n" + err) if err.strip() else "")


def main() -> None:
    print("=== before ===")
    print(ssh("uci -q get opennds.@opennds[0].faskey; echo; uci -q get nds-agent.main.device_id"))

    print("=== sync faskey ===")
    print(
        ssh(
            f"""
uci set opennds.@opennds[0].faskey='{FAS_KEY}'
uci set opennds.@opennds[0].fasremoteip='{CLOUD}'
uci set opennds.@opennds[0].fasport='8080'
uci set opennds.@opennds[0].faspath='/fas'
uci set opennds.@opennds[0].fas_secure_enabled='1'
uci set opennds.@opennds[0].gatewayname='{DEVICE_ID}'
uci set nds-agent.main.device_id='{DEVICE_ID}'
uci set nds-agent.main.device_secret='{SECRET}'
uci set nds-agent.main.cloud_url='http://{CLOUD}:8080'
uci commit opennds
uci commit nds-agent
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
/etc/init.d/opennds restart
sleep 3
echo faskey=$(uci -q get opennds.@opennds[0].faskey | head -c 24)...
ndsctl status 2>/dev/null | sed -n '1,18p'
"""
        )
    )

    payload = json.dumps(
        {"device_id": DEVICE_ID, "name": f"Newifi D2 {DEVICE_ID}", "secret": SECRET}
    ).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/v1/device/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            print("register", DEVICE_ID, r.status, r.read()[:200])
    except Exception as e:
        print("register:", e)

    print("=== restart cloud ===")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | "
            "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }",
        ],
        check=False,
    )
    time.sleep(2)
    env = os.environ.copy()
    for line in (ROOT / "cloud" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    env["USER_PORTAL_URL"] = f"http://{CLOUD}:8080/portal/"
    env["USER_WEB_DIR"] = str(ROOT / "user-web" / "dist")
    log = ROOT / "build" / "logs" / "cloud-dev.log"
    with open(log, "w", encoding="utf-8") as f:
        subprocess.Popen(
            ["go", "run", "./cmd/server"],
            cwd=str(ROOT / "cloud"),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    for _ in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2) as r:
                print("cloud", r.read().decode())
                break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("cloud start failed")

    print("portal_url", env["USER_PORTAL_URL"])
    print("fas_key synced", FAS_KEY[:16] + "...")


if __name__ == "__main__":
    main()
