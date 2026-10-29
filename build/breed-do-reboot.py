#!/usr/bin/env python3
"""Trigger Breed reboot via /rebooting.html then wait for OpenWrt."""
from __future__ import annotations

import re
import socket
import time

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"


def http(method: str, path: str, body: bytes = b"", ctype: str | None = None, timeout: float = 30) -> bytes:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if method == "POST":
        headers.append(f"Content-Length: {len(body)}")
        headers.append(f"Content-Type: {ctype or 'application/x-www-form-urlencoded'}")
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body
    s = socket.socket()
    s.settimeout(timeout)
    s.bind((LOCAL, 0))
    s.connect((HOST, 80))
    s.sendall(raw)
    out = b""
    while True:
        try:
            d = s.recv(65536)
        except TimeoutError:
            break
        if not d:
            break
        out += d
    s.close()
    return out


def body(raw: bytes) -> bytes:
    return raw.split(b"\r\n\r\n", 1)[-1]


def identify() -> str:
    try:
        b = body(http("GET", "/", timeout=4))
        if b"Breed" in b:
            return "breed"
        if b"LuCI" in b or b"OpenWrt" in b or b"luci" in b:
            return "openwrt"
        return "other"
    except OSError:
        return "down"


def main() -> int:
    html = body(http("GET", "/reboot.html")).decode("utf-8", "replace")
    m = re.search(r'name="magic"[^>]*value="(\d+)"', html)
    if not m:
        m = re.search(r'value="(\d+)"[^>]*name="magic"', html)
    magic = m.group(1) if m else None
    print("magic=", magic, "initial=", identify())
    if not magic:
        print("no magic; ask user to click Reboot in Breed")
        return 2

    payload = f"submit=Reboot&magic={magic}".encode()
    try:
        raw = http("POST", "/rebooting.html", payload, timeout=20)
        print("reboot post:", body(raw)[:300].decode("utf-8", "replace"))
    except OSError as e:
        print("reboot post err (often OK if already rebooting):", e)

    print("waiting OpenWrt...")
    for i in range(48):
        time.sleep(5)
        for host in (HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.bind((LOCAL, 0))
                s.connect((host, 22))
                ban = s.recv(40)
                if ban.startswith(b"SSH-"):
                    print("SUCCESS ssh", host, ban)
                    return 0
            except OSError:
                pass
            finally:
                s.close()
        mode = identify()
        print(f"{i+1} {mode}")
        if mode == "openwrt":
            print("SUCCESS openwrt http")
            return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
