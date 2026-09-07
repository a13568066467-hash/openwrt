#!/usr/bin/env python3
"""Flash Newifi D2 from Breed via LAN, binding to the PC Ethernet IP to bypass VPN hijacks."""
from __future__ import annotations

import argparse
import re
import socket
import time
from pathlib import Path

BREED_HOST = "192.168.1.1"
LOCAL_IP = "192.168.1.2"
FW = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "images"
    / "openwrt-ramips-mt7621-d-team_newifi-d2-squashfs-sysupgrade.bin"
)


def http_exchange(
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> tuple[int, bytes, bytes]:
    """HTTP/1.0 over a socket bound to LOCAL_IP (avoids Meta/VPN fake routes)."""
    hdrs = {"Host": BREED_HOST, "Connection": "close"}
    if headers:
        hdrs.update(headers)
    if body:
        hdrs["Content-Length"] = str(len(body))
    req = [f"{method} {path} HTTP/1.0"]
    req.extend(f"{k}: {v}" for k, v in hdrs.items())
    raw = ("\r\n".join(req) + "\r\n\r\n").encode() + body

    s = socket.socket()
    s.settimeout(timeout)
    s.bind((LOCAL_IP, 0))
    s.connect((BREED_HOST, 80))
    s.sendall(raw)
    chunks: list[bytes] = []
    while True:
        try:
            d = s.recv(65536)
        except TimeoutError:
            break
        if not d:
            break
        chunks.append(d)
    s.close()
    data = b"".join(chunks)
    if b"\r\n\r\n" not in data:
        return 0, b"", data
    head, resp_body = data.split(b"\r\n\r\n", 1)
    m = re.match(rb"HTTP/\d\.\d\s+(\d+)", head)
    code = int(m.group(1)) if m else 0
    return code, head, resp_body


def is_breed(body: bytes) -> bool:
    return b"Breed" in body or b"Server: Breed" in body


def probe() -> str:
    try:
        code, head, body = http_exchange("GET", "/", timeout=5)
    except OSError as e:
        return f"down:{e}"
    if is_breed(head + body):
        return "breed"
    if b"LuCI" in body or b"OpenWrt" in body or b"luci-static" in body:
        return "openwrt"
    return f"other:{code}:{body[:80]!r}"


def flash(fw: Path) -> None:
    data = fw.read_bytes()
    print(f"firmware={fw.name} size={len(data)}")
    boundary = "----BreedUploadBoundaryYyZ"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode() + b"\r\n")

    def file_field(name: str, filename: str, content: bytes) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        chunks.append(content + b"\r\n")

    # Generic firmware only; keep bootloader/EEPROM; auto-reboot after flash.
    field("fw_check", "1")
    file_field("fw_file", fw.name, data)
    field("flash_layout", "reference")
    field("fw_type", "generic")
    field("autoreboot", "1")
    field("skipboot", "1")
    field("skipeeprom", "1")
    field("submit", "Upload")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)

    print("uploading to Breed /upload.html ...")
    code, head, resp = http_exchange(
        "POST",
        "/upload.html",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=300,
    )
    print(f"upload HTTP {code}, response {len(resp)} bytes")
    text = resp.decode("utf-8", "replace")
    print(text[:1500])

    magic = re.search(r'name="magic"\s+value="(\d+)"', text)
    action = re.search(r'<form[^>]+action="([^"]+)"', text)
    if not magic:
        print("no confirm magic — Breed may flash automatically with autoreboot")
        return

    action_path = action.group(1) if action else "/flashing.html"
    if not action_path.startswith("/"):
        action_path = "/" + action_path
    print(f"confirming flash {action_path} magic={magic.group(1)}")
    boundary2 = "----BreedFlashBoundary"
    confirm = "\r\n".join(
        [
            f"--{boundary2}",
            'Content-Disposition: form-data; name="submit"',
            "",
            "Flash",
            f"--{boundary2}",
            'Content-Disposition: form-data; name="magic"',
            "",
            magic.group(1),
            f"--{boundary2}--",
            "",
        ]
    ).encode()
    try:
        code, _, resp = http_exchange(
            "POST",
            action_path,
            body=confirm,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary2}"},
            timeout=300,
        )
        print(f"confirm HTTP {code}")
        print(resp[:800].decode("utf-8", "replace"))
    except OSError as e:
        print(f"confirm connection dropped (often normal during flash): {e}")


def wait_openwrt(seconds: int = 240) -> str:
    deadline = time.time() + seconds
    last = ""
    while time.time() < deadline:
        mode = probe()
        if mode != last:
            print(f"mode={mode}")
            last = mode
        if mode == "openwrt":
            return mode
        # After flash, Breed disappears then OpenWrt comes up; also try SSH banner.
        for host in (BREED_HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.bind((LOCAL_IP, 0))
                s.connect((host, 22))
                banner = s.recv(80)
                if banner.startswith(b"SSH-"):
                    print(f"SSH banner on {host}: {banner!r}")
                    return "openwrt"
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(4)
    return probe()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fw", type=Path, default=FW)
    parser.add_argument("--local-ip", default="192.168.1.2")
    args = parser.parse_args()

    global LOCAL_IP
    LOCAL_IP = args.local_ip

    mode = probe()
    print(f"initial={mode} local={LOCAL_IP}")
    if mode == "openwrt":
        print("already OpenWrt")
        return 0
    if mode != "breed":
        print("Breed not reachable on bound LAN path; abort")
        return 2
    if not args.fw.is_file():
        print(f"missing firmware: {args.fw}")
        return 3

    flash(args.fw)
    print("waiting for OpenWrt after flash...")
    final = wait_openwrt(240)
    print(f"final={final}")
    return 0 if final == "openwrt" else 1


if __name__ == "__main__":
    raise SystemExit(main())
