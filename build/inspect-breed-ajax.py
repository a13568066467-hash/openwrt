#!/usr/bin/env python3
"""Inspect Breed upgrade AJAX endpoints (LAN-bound)."""
from __future__ import annotations

import re
import socket
from pathlib import Path

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"
OUT = Path(r"d:\Users\Documents\project\openwrt\build\logs")
OUT.mkdir(parents=True, exist_ok=True)


def http(method: str, path: str, body: bytes = b"", content_type: str | None = None, timeout: float = 30) -> bytes:
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
    return raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw


def main() -> None:
    for path in ("/ajax.js", "/upgrading.html", "/upload.html", "/style.css"):
        raw = http("GET", path)
        b = body(raw)
        (OUT / path.lstrip("/").replace("/", "_")).write_bytes(b)
        print(f"{path}: http_bytes={len(raw)} body={len(b)}")
        if path.endswith(".js") or path.endswith(".html"):
            text = b.decode("utf-8", "replace")
            # interesting endpoints
            urls = sorted(set(re.findall(r'["\'](/[^"\']+)["\']', text)))
            print("  paths:", urls[:40])
            for kw in ("upgrade", "progress", "flash", "xmlhttp", "ajax", "percent", "Firmware"):
                if kw.lower() in text.lower():
                    print(f"  has {kw}")
            print("--- snippet ---")
            print(text[:1200])
            print("---------------")


if __name__ == "__main__":
    main()
