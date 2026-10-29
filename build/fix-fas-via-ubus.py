#!/usr/bin/env python3
"""Set opennds faskey via LuCI/ubus HTTP (bound to LAN)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"d:\Users\Documents\project\openwrt")
LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
PASS = os.environ["NDS_ROUTER_PASSWORD"]
CLOUD = os.environ.get("NDS_CLOUD_HOST", "192.168.1.125")
FAS_KEY = os.environ["NDS_FAS_KEY"]
DEVICE_ID = os.environ.get("NDS_DEVICE_ID", "NewWiFI")
SECRET = os.environ["NDS_DEVICE_SECRET"]


def http(method: str, path: str, body: bytes = b"", content_type: str | None = None, timeout: float = 30) -> tuple[int, bytes]:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if body:
        headers.append(f"Content-Length: {len(body)}")
    if content_type:
        headers.append(f"Content-Type: {content_type}")
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body
    s = socket.socket()
    s.settimeout(timeout)
    s.bind((LOCAL, 0))
    s.connect((HOST, 80))
    s.sendall(raw)
    data = b""
    while True:
        try:
            c = s.recv(65536)
        except TimeoutError:
            break
        if not c:
            break
        data += c
    s.close()
    if b"\r\n\r\n" not in data:
        return 0, data
    head, body_b = data.split(b"\r\n\r\n", 1)
    code = int(head.split(b" ", 2)[1])
    return code, body_b


def ubus(session: str | None, obj: str, method: str, params: dict | None = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "call",
        "params": [session or "00000000000000000000000000000000", obj, method, params or {}],
    }
    code, body = http("POST", "/ubus", json.dumps(payload).encode(), "application/json")
    data = json.loads(body.decode("utf-8", "replace"))
    print(f"ubus {obj}.{method} http={code} -> {json.dumps(data, ensure_ascii=False)[:240]}")
    return data


def main() -> None:
    login = ubus(None, "session", "login", {"username": "root", "password": PASS})
    sid = login["result"][1]["ubus_rpc_session"]

    # Find opennds section
    cfg = ubus(sid, "uci", "get", {"config": "opennds"})
    # set values
    ubus(
        sid,
        "uci",
        "set",
        {
            "config": "opennds",
            "section": "@opennds[0]",
            "values": {
                "faskey": FAS_KEY,
                "fasremoteip": CLOUD,
                "fasport": "8080",
                "faspath": "/fas",
                "fas_secure_enabled": "1",
            },
        },
    )
    ubus(sid, "uci", "commit", {"config": "opennds"})

    # restart opennds via luci or service
    # try system.exec if available
    for attempt in (
        {"command": "/etc/init.d/opennds restart"},
        {"command": "/etc/init.d/opennds restart", "env": {}},
    ):
        try:
            r = ubus(sid, "file", "exec", {"command": "/etc/init.d/opennds", "params": ["restart"]})
            break
        except Exception as e:
            print("exec fail", e)

    # Also try rc.common via luci-rpc
    ubus(sid, "rc", "init", {"name": "opennds", "action": "restart"})

    time.sleep(4)
    # verify via uci get
    got = ubus(sid, "uci", "get", {"config": "opennds", "section": "@opennds[0]", "option": "faskey"})
    print("faskey result", got)

    # register router
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
            print("register", r.status, r.read()[:200])
    except Exception as e:
        print("register:", e)

    # restart cloud
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
        raise SystemExit("cloud failed")
    print("DONE portal=", env["USER_PORTAL_URL"], "device_id=", DEVICE_ID)


if __name__ == "__main__":
    main()
