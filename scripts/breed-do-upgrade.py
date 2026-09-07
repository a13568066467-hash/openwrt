#!/usr/bin/env python3
"""Trigger Breed flash after upload confirm page (GET /upgrading.html)."""
from __future__ import annotations

import re
import socket
import time
from pathlib import Path

LOCAL = "192.168.1.2"
HOST = "192.168.1.1"
FW = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "images"
    / "openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin"
)


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


def upload() -> None:
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
    raw = http("POST", "/upload.html", b"".join(parts), f"multipart/form-data; boundary={boundary}")
    b = body_of(raw)
    if b"upgrading.html" not in b and b"upgrade_confirm" not in b:
        raise RuntimeError(f"unexpected upload response: {b[:200]!r}")
    print("upload OK, confirm page received")


def main() -> int:
    # Ensure session has uploaded firmware, then trigger flash.
    print("re-upload then trigger /upgrading.html")
    upload()
    print("GET /upgrading.html")
    try:
        raw = http("GET", "/upgrading.html", timeout=300)
        print(raw[:500])
        print(body_of(raw)[:800].decode("utf-8", "replace"))
    except OSError as e:
        print(f"upgrading connection: {e}")

    print("waiting for OpenWrt (up to 4 min)...")
    deadline = time.time() + 240
    while time.time() < deadline:
        try:
            raw = http("GET", "/", timeout=4)
            if b"Breed" in raw:
                print("still breed")
            else:
                b = body_of(raw)
                if b"LuCI" in b or b"OpenWrt" in b or b"luci" in b:
                    print("SUCCESS openwrt http")
                    return 0
                print("http other", b[:80])
        except OSError:
            print("http down")
        for host in (HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                # After flash LAN IP of PC may change; try unbound connect too.
                try:
                    s.bind((LOCAL, 0))
                except OSError:
                    pass
                s.connect((host, 22))
                ban = s.recv(64)
                if ban.startswith(b"SSH-"):
                    print(f"SUCCESS ssh {host} {ban!r}")
                    return 0
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(5)
    print("FAIL timeout")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
