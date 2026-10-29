#!/usr/bin/env python3
"""Upload FW to Breed, dump confirm page, find AJAX flash trigger."""
from __future__ import annotations

import re
import socket
import time
from pathlib import Path

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"
FW = Path(
    r"d:\Users\Documents\project\openwrt\build\images"
    r"\openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin"
)
OUT = Path(r"d:\Users\Documents\project\openwrt\build\logs")
OUT.mkdir(parents=True, exist_ok=True)


def http(method: str, path: str, body: bytes = b"", content_type: str | None = None, timeout: float = 300) -> bytes:
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


def body_of(raw: bytes) -> bytes:
    return raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw


def upload() -> bytes:
    data = FW.read_bytes()
    boundary = "----BreedUploadBoundaryYyZ"
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode() + b"\r\n")

    def file_field(name: str, filename: str, content: bytes) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        parts.append(content + b"\r\n")

    field("fw_check", "1")
    file_field("fw_file", FW.name, data)
    field("flash_layout", "reference")
    field("fw_type", "generic")
    field("autoreboot", "1")
    field("skipboot", "1")
    field("skipeeprom", "1")
    field("submit", "Upload")
    parts.append(f"--{boundary}--\r\n".encode())
    print(f"uploading {len(data)} bytes...")
    return http("POST", "/upload.html", b"".join(parts), f"multipart/form-data; boundary={boundary}", timeout=300)


def main() -> int:
    raw = upload()
    html = body_of(raw)
    (OUT / "breed_confirm.html").write_bytes(html)
    text = html.decode("utf-8", "replace")
    print("confirm len", len(html))
    print(text)
    print("==== links/forms ====")
    print("hrefs", re.findall(r'href=["\']([^"\']+)["\']', text, re.I))
    print("actions", re.findall(r'action=["\']([^"\']+)["\']', text, re.I))
    print("onclicks", re.findall(r'onclick=["\']([^"\']+)["\']', text, re.I))
    print("RequestURL", re.findall(r'RequestURL\(([^)]+)\)', text))
    print("scripts src", re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.I))
    # inline scripts
    for m in re.finditer(r'<script[^>]*>(.*?)</script>', text, re.I | re.S):
        print("--- script ---")
        print(m.group(1)[:2000])

    # If confirm redirects to upgrading.html with query, try that
    print("==== GET /upgrading.html right after upload ====")
    up = http("GET", "/upgrading.html", timeout=30)
    ub = body_of(up)
    (OUT / "breed_upgrading_after_upload.html").write_bytes(ub)
    print(ub.decode("utf-8", "replace")[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
