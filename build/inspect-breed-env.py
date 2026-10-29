#!/usr/bin/env python3
"""Dump Breed env / upgrade pages to diagnose boot-after-flash failure."""
from __future__ import annotations

import re
import socket
from pathlib import Path

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"
OUT = Path(r"d:\Users\Documents\project\openwrt\build\logs")
OUT.mkdir(parents=True, exist_ok=True)


def http(method: str, path: str, body: bytes = b"", ctype: str | None = None, timeout: float = 20) -> bytes:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if method == "POST":
        headers.append(f"Content-Length: {len(body)}")
        headers.append(f"Content-Type: {ctype or 'application/x-www-form-urlencoded'}")
        headers.append("Cache-Control: no-cache")
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


def main() -> None:
    pages = [
        "/",
        "/index.html",
        "/upgrade.html",
        "/envedit.html",
        "/envconf.html",
        "/about.html",
        "/backup.html",
    ]
    for path in pages:
        try:
            b = body(http("GET", path))
        except OSError as e:
            print(path, "FAIL", e)
            continue
        name = path.strip("/").replace("/", "_") or "root"
        (OUT / f"breed_{name}.html").write_bytes(b)
        text = b.decode("utf-8", "replace")
        print(f"\n==== {path} len={len(b)} ====")
        # print tables / forms / env-looking lines
        if "env" in path or path in ("/", "/index.html"):
            print(text[:2500])
        else:
            # extract select options and checkboxes
            opts = re.findall(r"<option[^>]*>([^<]+)</option>", text, re.I)
            checks = re.findall(r'name="([^"]+)"[^>]*(checked|value="[^"]*")', text, re.I)
            print("options:", opts[:30])
            print("inputs:", re.findall(r'<input[^>]+>', text, re.I)[:40])
            print("selects:", re.findall(r'<select[^>]*>.*?</select>', text, re.I | re.S)[:5])
            if len(text) < 4000:
                print(text)


if __name__ == "__main__":
    main()
