#!/usr/bin/env python3
"""Newifi D2 Breed: factory-reset Config(公版) then flash sysupgrade with progress poll."""
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


def http(method: str, path: str, body: bytes = b"", ctype: str | None = None, timeout: float = 120) -> bytes:
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


def post_query(path: str) -> str:
    return body(http("POST", path, b"", timeout=30)).decode("utf-8", "replace").strip()


def poll_progress(query_path: str, label: str, seconds: int = 180) -> bool:
    print(f"polling {query_path} ({label})...")
    last = ""
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status = post_query(query_path)
        except OSError as e:
            print("query err", e)
            time.sleep(1)
            continue
        if status != last:
            print("progress:", repr(status)[:120])
            last = status
        if status in {"100", "done", "OK", "ok"} or "完成" in status:
            return True
        try:
            if int(status) >= 100:
                return True
        except ValueError:
            pass
        if status in {"CE", "SE", "BE"}:
            time.sleep(1)
            continue
        time.sleep(1)
    print("WARN poll timeout last=", repr(last))
    return False


def factory_reset_config_ref() -> None:
    print("=== 1) factory reset Config(公版) ===")
    payload = b"flash_layout=CONFIG-REF&submit=Execute"
    raw = http("POST", "/erasing.html", payload, timeout=60)
    b = body(raw)
    print("erasing page bytes", len(b))
    # Guess query endpoints used by Breed erase UI
    text = b.decode("utf-8", "replace")
    if "erase_query" in text or "query" in text:
        print("page snippet has query refs")
    for qp in ("/erase_query.html", "/erasing_query.html", "/upgrade_query.html"):
        try:
            s = post_query(qp)
            print(qp, "->", repr(s)[:80])
            if s not in {"", "CE", "SE", "BE"} and "未找到" not in s and "not found" not in s.lower():
                poll_progress(qp, "erase", 120)
                break
        except OSError as e:
            print(qp, "fail", e)
    time.sleep(2)


def upload_and_flash() -> None:
    print("=== 2) upload + flash sysupgrade ===")
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
    field("flash_layout", "reference")  # 公版 0x50000
    field("fw_type", "generic")
    field("autoreboot", "1")
    field("skipboot", "1")
    field("skipeeprom", "1")
    field("submit", "Upload")
    parts.append(f"--{boundary}--\r\n".encode())
    print(f"uploading {len(data)} bytes...")
    raw = http(
        "POST",
        "/upload.html",
        b"".join(parts),
        f"multipart/form-data; boundary={boundary}",
        timeout=300,
    )
    b = body(raw)
    if b"has_fw" not in b and b"upgrading.html" not in b:
        raise RuntimeError(f"upload unexpected: {b[:200]!r}")
    print("upload OK, start upgrading.html")
    http("GET", "/upgrading.html", timeout=60)
    ok = poll_progress("/upgrade_query.html", "flash", 300)
    print("flash poll ok=", ok)


def wait_openwrt(seconds: int = 600) -> bool:
    print(f"=== 3) wait OpenWrt up to {seconds}s ===")
    deadline = time.time() + seconds
    n = 0
    while time.time() < deadline:
        n += 1
        # SSH
        for host in (HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.bind((LOCAL, 0))
                s.connect((host, 22))
                ban = s.recv(40)
                if ban.startswith(b"SSH-"):
                    print("SUCCESS ssh", host, ban)
                    return True
            except OSError:
                pass
            finally:
                s.close()
        # HTTP
        try:
            b = body(http("GET", "/", timeout=3))
            if b"Breed" in b:
                print(n, "breed")
            elif b"LuCI" in b or b"OpenWrt" in b or b"luci" in b:
                print("SUCCESS openwrt http")
                return True
            else:
                print(n, "http other", b[:40])
        except OSError:
            print(n, "down")
        time.sleep(5)
    return False


def main() -> int:
    factory_reset_config_ref()
    upload_and_flash()
    if wait_openwrt(600):
        return 0
    print("FAIL: still not OpenWrt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
