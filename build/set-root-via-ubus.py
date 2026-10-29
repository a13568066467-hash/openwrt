#!/usr/bin/env python3
"""Set OpenWrt root password via ubus (empty first-boot login)."""
from __future__ import annotations

import json
import socket
import time
import os

import paramiko

LOCAL = os.environ.get("NDS_LOCAL_IP", "192.168.1.125")
HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
NEW_PASS = os.environ["NDS_ROUTER_PASSWORD"]


def http(method: str, path: str, body: bytes = b"", content_type: str | None = None) -> tuple[int, bytes]:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if body:
        headers.append(f"Content-Length: {len(body)}")
    if content_type:
        headers.append(f"Content-Type: {content_type}")
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body
    s = socket.socket()
    s.settimeout(15)
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
    if b"\r\n\r\n" in data:
        head, body_b = data.split(b"\r\n\r\n", 1)
        m = head.split(b" ", 2)
        code = int(m[1]) if len(m) > 1 else 0
        return code, body_b
    return 0, data


def ubus_call(session: str | None, obj: str, method: str, params: dict | None = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "call",
        "params": [session or "00000000000000000000000000000000", obj, method, params or {}],
    }
    code, body = http(
        "POST",
        "/ubus",
        json.dumps(payload).encode(),
        "application/json",
    )
    data = json.loads(body.decode("utf-8", "replace"))
    if code != 200 and "error" in data:
        raise RuntimeError(data)
    return data


def main() -> int:
    print("login empty...")
    login = ubus_call(None, "session", "login", {"username": "root", "password": ""})
    print(json.dumps(login, ensure_ascii=False)[:400])
    result = login.get("result")
    if not isinstance(result, list) or len(result) < 2 or result[0] != 0:
        raise RuntimeError(f"login failed: {login}")
    sid = result[1]["ubus_rpc_session"]
    print("sid", sid[:12], "...")

    print("setPassword...")
    sp = ubus_call(sid, "luci", "setPassword", {"username": "root", "password": NEW_PASS})
    print(sp)

    # give dropbear a moment
    time.sleep(2)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username="root",
        password=NEW_PASS,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    _, o, _ = c.exec_command(
        "cat /etc/openwrt_release; opkg list-installed 2>/dev/null | grep -E 'opennds|nds-' || true"
    )
    print(o.read().decode())
    c.close()
    print("SSH OK with new password")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
