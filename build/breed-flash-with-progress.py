#!/usr/bin/env python3
"""Complete Breed flash: poll /upgrade_query.html like the browser AJAX does."""
from __future__ import annotations

import socket
import time
from pathlib import Path

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"
FW = Path(
    r"d:\Users\Documents\project\openwrt\build\images"
    r"\openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin"
)


def http(
    method: str,
    path: str,
    body: bytes = b"",
    content_type: str | None = None,
    timeout: float = 120,
) -> bytes:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if body is not None and method != "GET":
        # RequestURL sends empty body with form content-type
        headers.append(f"Content-Length: {len(body)}")
        if content_type:
            headers.append(f"Content-Type: {content_type}")
        elif method == "POST":
            headers.append("Content-Type: application/x-www-form-urlencoded")
            headers.append("Cache-Control: no-cache")
    elif method == "POST":
        headers.append("Content-Length: 0")
        headers.append("Content-Type: application/x-www-form-urlencoded")
        headers.append("Cache-Control: no-cache")
    if method == "GET" and body:
        headers.append(f"Content-Length: {len(body)}")
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
    print(f"upload {len(data)} bytes...")
    raw = http(
        "POST",
        "/upload.html",
        b"".join(parts),
        f"multipart/form-data; boundary={boundary}",
        timeout=300,
    )
    b = body_of(raw)
    if b"upgrading.html" not in b and b"upgrade_confirm" not in b and b"has_fw" not in b:
        raise RuntimeError(f"unexpected upload: {b[:200]!r}")
    print("upload OK")


def upgrade_query() -> str:
    # Mimic RequestURL: POST with empty body
    raw = http("POST", "/upgrade_query.html", b"", timeout=30)
    return body_of(raw).decode("utf-8", "replace").strip()


def wait_openwrt(seconds: int = 420) -> bool:
    print(f"waiting OpenWrt up to {seconds}s...")
    deadline = time.time() + seconds
    while time.time() < deadline:
        # HTTP
        try:
            raw = http("GET", "/", timeout=4)
            b = body_of(raw)
            if b"Breed" in b:
                print("still breed")
            elif b"LuCI" in b or b"OpenWrt" in b or b"luci" in b:
                print("SUCCESS openwrt http")
                return True
            else:
                print("http other", b[:60])
        except OSError as e:
            print("http down", type(e).__name__)
        # SSH
        for host in (HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.bind((LOCAL, 0))
                s.connect((host, 22))
                ban = s.recv(64)
                if ban.startswith(b"SSH-"):
                    print(f"SUCCESS ssh {host} {ban!r}")
                    return True
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(5)
    return False


def main() -> int:
    # If a previous upload is still pending, try query first; else re-upload.
    status = ""
    try:
        # Ensure upgrading page exists (starts flash on many Breed builds)
        up = body_of(http("GET", "/upgrading.html", timeout=30))
        print("upgrading page:", up[:120].decode("utf-8", "replace").replace("\n", " "))
        if b"\xe6\x96\x87\xe4\xbb\xb6\xe6\x9c\xaa\xe6\x89\xbe\xe5\x88\xb0" in up or b"file" in up.lower() and b"not" in up.lower():
            print("no pending fw, re-upload")
            upload()
            up = body_of(http("GET", "/upgrading.html", timeout=60))
            print("upgrading after upload ok", len(up))
    except OSError as e:
        print("need upload:", e)
        upload()
        http("GET", "/upgrading.html", timeout=60)

    print("polling /upgrade_query.html ...")
    last = ""
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            status = upgrade_query()
        except OSError as e:
            print("query err", e)
            time.sleep(2)
            continue
        if status != last:
            print("progress:", repr(status)[:200])
            last = status
        # Common Breed responses: "0".."100", "done", Chinese done prompt fragments
        if status in {"100", "done", "OK", "ok"} or status.endswith("%") and status.startswith("100"):
            print("flash reached 100%")
            break
        if "完成" in status or "重启" in status:
            print("flash done message")
            break
        if status in {"CE", "SE", "BE"}:
            print("ajax transport error", status)
        # numeric progress
        try:
            if int(status) >= 100:
                print("flash >=100")
                break
        except ValueError:
            pass
        time.sleep(1)
    else:
        print("WARN: progress poll timeout, last=", repr(last))

    if wait_openwrt(480):
        return 0
    print("FAIL: OpenWrt not up")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
