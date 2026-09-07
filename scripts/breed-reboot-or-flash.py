#!/usr/bin/env python3
"""Reboot Newifi from Breed; if still in Breed, flash sysupgrade firmware."""
from __future__ import annotations

import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BREED = "http://192.168.1.1"
FW = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "images"
    / "openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin"
)


def http_get(path: str, timeout: float = 4.0) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(BREED + path, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""
    except Exception as e:  # noqa: BLE001
        raise e


def is_breed(body: bytes) -> bool:
    return b"Breed" in body or b"breed_console" in body


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def probe_mode() -> str:
    """Return breed|openwrt|down|unknown.

    Do not trust bare TCP connect — VPN/proxy layers (e.g. Meta) often fake-open
    22/80. Require a real HTTP body fingerprint.
    """
    # Prefer real HTTP fingerprints over TCP connect.
    for host in ("192.168.1.1", "192.168.10.1"):
        try:
            with urllib.request.urlopen(f"http://{host}/", timeout=3) as r:
                body = r.read(800)
        except Exception:
            continue
        if is_breed(body):
            return "breed"
        # LuCI / OpenWrt splash / our portal markers
        if (
            b"LuCI" in body
            or b"OpenWrt" in body
            or b"openwrt" in body
            or b"luci-static" in body
            or b"cgi-bin/luci" in body
        ):
            return "openwrt"
        # Non-breed HTTP that isn't OpenWrt (OEM / intercepted) — keep probing.
        return "unknown"

    if tcp_open("192.168.1.1", 80) or tcp_open("192.168.10.1", 80):
        return "unknown"
    return "down"


def breed_reboot() -> None:
    boundary = "----BreedBoundary7MA4YWxkTrZu0gW"
    parts = [
        f"--{boundary}",
        'Content-Disposition: form-data; name="submit"',
        "",
        "Reboot",
        f"--{boundary}",
        'Content-Disposition: form-data; name="magic"',
        "",
        "108599",
        f"--{boundary}--",
        "",
    ]
    body = "\r\n".join(parts).encode()
    req = urllib.request.Request(
        BREED + "/rebooting.html",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"reboot POST status={r.status}")
            print(r.read(300).decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        # Device often drops connection immediately on reboot — that's OK.
        print(f"reboot POST: {type(e).__name__}: {e}")


def wait_mode(seconds: int = 120) -> str:
    deadline = time.time() + seconds
    last = ""
    while time.time() < deadline:
        mode = probe_mode()
        if mode != last:
            print(f"[{int(time.time())}] mode={mode}")
            last = mode
        if mode in ("openwrt", "breed"):
            # after reboot, breed briefly disappears then may return
            if mode == "openwrt":
                return mode
            # if still breed after we expected boot, keep waiting a bit more
        time.sleep(3)
    return probe_mode()


def breed_upload_firmware(fw_path: Path) -> None:
    if not fw_path.is_file():
        raise FileNotFoundError(fw_path)
    data = fw_path.read_bytes()
    print(f"uploading {fw_path.name} ({len(data)} bytes)")

    boundary = "----BreedUploadBoundaryYyZ"
    # Generic firmware flash: fw only, skip bootloader/eeprom, autoreboot, reference layout
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode() + b"\r\n")

    def add_file(name: str, filename: str, content: bytes) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        chunks.append(content + b"\r\n")

    add_field("fw_check", "1")
    add_file("fw_file", fw_path.name, data)
    add_field("flash_layout", "reference")
    add_field("fw_type", "generic")
    add_field("autoreboot", "1")
    add_field("skipboot", "1")
    add_field("skipeeprom", "1")
    add_field("submit", "Upload")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)

    req = urllib.request.Request(
        BREED + "/upload.html",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = r.read()
        print(f"upload status={r.status} len={len(resp)}")
        text = resp.decode("utf-8", "replace")
        print(text[:2000])
        return text


def maybe_confirm_flash(upload_html: str) -> None:
    # Breed may return a confirm page with form action flashing.html and a magic value.
    import re

    magic = re.search(r'name="magic"\s+value="(\d+)"', upload_html)
    action = re.search(r'<form[^>]+action="([^"]+)"', upload_html)
    if not magic:
        print("no magic in upload response — may already be flashing / done")
        return
    action_path = action.group(1) if action else "/flashing.html"
    if not action_path.startswith("/"):
        action_path = "/" + action_path
    print(f"confirm flash action={action_path} magic={magic.group(1)}")
    boundary = "----BreedFlashBoundary"
    parts = [
        f"--{boundary}",
        'Content-Disposition: form-data; name="submit"',
        "",
        "Flash",
        f"--{boundary}",
        'Content-Disposition: form-data; name="magic"',
        "",
        magic.group(1),
        f"--{boundary}--",
        "",
    ]
    body = "\r\n".join(parts).encode()
    req = urllib.request.Request(
        BREED + action_path,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            print(f"flash confirm status={r.status}")
            print(r.read(800).decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"flash confirm: {type(e).__name__}: {e}")


def main() -> int:
    mode = probe_mode()
    print(f"initial mode={mode}")
    if mode == "openwrt":
        print("already OpenWrt — nothing to do")
        return 0
    if mode != "breed":
        print("device not reachable as Breed; abort")
        return 2

    print("=== step1: Breed reboot ===")
    breed_reboot()
    print("waiting up to 90s for OpenWrt...")
    mode = wait_mode(90)
    print(f"after reboot mode={mode}")
    if mode == "openwrt":
        print("SUCCESS: OpenWrt is up")
        return 0

    if mode != "breed":
        # still booting?
        print("waiting another 60s...")
        mode = wait_mode(60)
        print(f"delayed mode={mode}")
        if mode == "openwrt":
            print("SUCCESS: OpenWrt is up")
            return 0

    if mode != "breed":
        print(f"unexpected mode={mode}; not flashing blindly")
        return 3

    print("=== step2: still Breed — flash sysupgrade ===")
    html = breed_upload_firmware(FW)
    maybe_confirm_flash(html)
    print("waiting up to 180s after flash...")
    mode = wait_mode(180)
    print(f"final mode={mode}")
    if mode == "openwrt":
        print("SUCCESS: OpenWrt after flash")
        return 0
    print("FAIL: still not OpenWrt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
