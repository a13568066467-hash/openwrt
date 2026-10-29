#!/usr/bin/env python3
"""Dump Breed reset.html and optionally run Config(公版) factory reset."""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"
OUT = Path(r"d:\Users\Documents\project\openwrt\build\logs")


def http(method: str, path: str, body: bytes = b"", ctype: str | None = None, timeout: float = 60) -> bytes:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if method == "POST":
        headers.append(f"Content-Length: {len(body)}")
        headers.append(f"Content-Type: {ctype or 'multipart/form-data'}")
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
    return raw.split(b"\r\n\r\n", 1)[-1] if b"\r\n\r\n" in raw else raw


def main() -> int:
    raw = http("GET", "/reset.html")
    html = body(raw).decode("utf-8", "replace")
    (OUT / "breed_reset.html").write_text(html, encoding="utf-8")
    print(html)
    print("==== parsed ====")
    print("options", re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', html, re.I))
    print("magic", re.findall(r'name="magic"[^>]*value="([^"]*)"', html))
    print("actions", re.findall(r'action="([^"]*)"', html))
    if "--dump-only" in sys.argv:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
