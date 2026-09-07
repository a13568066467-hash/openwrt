#!/usr/bin/env python3
"""Upload firmware to Breed and confirm flash (bound to LAN IP)."""
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
OUT = Path(__file__).resolve().parents[1] / "scripts" / "_breed_confirm.html"


def http(method: str, path: str, body: bytes = b"", content_type: str | None = None, timeout: float = 300) -> bytes:
    headers = [
        f"{method} {path} HTTP/1.0",
        f"Host: {HOST}",
        "Connection: close",
    ]
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
    return b"".join(chunks)


def split_http(data: bytes) -> tuple[int, bytes]:
    if b"\r\n\r\n" not in data:
        return 0, data
    head, body = data.split(b"\r\n\r\n", 1)
    m = re.match(rb"HTTP/\d\.\d\s+(\d+)", head)
    return (int(m.group(1)) if m else 0), body


def main() -> int:
    data = FW.read_bytes()
    print(f"fw={FW.name} size={len(data)}")
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
    body = b"".join(parts)

    print("POST /upload.html")
    raw = http("POST", "/upload.html", body, f"multipart/form-data; boundary={boundary}")
    OUT.write_bytes(raw)
    code, html = split_http(raw)
    text = html.decode("utf-8", "replace")
    print(f"upload HTTP {code} body={len(html)}")

    # Breed confirm page uses various patterns; dump candidates.
    for pat in [
        r'name="magic"[^>]*value="([^"]+)"',
        r'value="([^"]+)"[^>]*name="magic"',
        r'name=\'magic\'[^>]*value=\'([^\']+)\'',
        r"magic=(\d+)",
    ]:
        m = re.search(pat, text, re.I)
        if m:
            print(f"magic via {pat}: {m.group(1)}")

    # Find all hidden inputs
    hiddens = re.findall(
        r'<input[^>]+type=["\']hidden["\'][^>]*>',
        text,
        re.I,
    )
    print("hidden inputs:")
    for h in hiddens:
        print(" ", h)

    forms = re.findall(r'<form[^>]*>.*?</form>', text, re.I | re.S)
    print(f"forms={len(forms)}")
    for i, f in enumerate(forms):
        print(f"--- form {i} ---")
        print(f[:1200])

    # Prefer form that mentions Flash / flashing
    target = None
    for f in forms:
        if "flash" in f.lower() or "Flash" in f or "magic" in f:
            target = f
            break
    if target is None and forms:
        target = forms[-1]

    if not target:
        print("no form found; abort")
        return 2

    action_m = re.search(r'action=["\']([^"\']+)["\']', target, re.I)
    action = action_m.group(1) if action_m else "/flashing.html"
    if not action.startswith("/"):
        action = "/" + action

    fields = {}
    for inp in re.findall(r"<input[^>]*>", target, re.I):
        nm = re.search(r'name=["\']([^"\']+)["\']', inp, re.I)
        if not nm:
            continue
        val_m = re.search(r'value=["\']([^"\']*)["\']', inp, re.I)
        fields[nm.group(1)] = val_m.group(1) if val_m else ""
    # button values
    for btn in re.findall(r"<button[^>]*>.*?</button>", target, re.I | re.S):
        nm = re.search(r'name=["\']([^"\']+)["\']', btn, re.I)
        val_m = re.search(r'value=["\']([^"\']*)["\']', btn, re.I)
        if nm:
            fields[nm.group(1)] = val_m.group(1) if val_m else "Flash"
    if "submit" not in fields:
        fields["submit"] = "Flash"

    print(f"confirm action={action} fields={fields}")

    boundary2 = "----BreedFlashConfirm"
    cparts: list[bytes] = []
    for k, v in fields.items():
        cparts.append(f"--{boundary2}\r\n".encode())
        cparts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        cparts.append(str(v).encode() + b"\r\n")
    cparts.append(f"--{boundary2}--\r\n".encode())
    cbody = b"".join(cparts)

    print(f"POST {action}")
    try:
        raw2 = http("POST", action, cbody, f"multipart/form-data; boundary={boundary2}", timeout=300)
        code2, body2 = split_http(raw2)
        print(f"confirm HTTP {code2}")
        print(body2[:1000].decode("utf-8", "replace"))
    except OSError as e:
        print(f"confirm dropped: {e} (often OK while flashing)")

    print("waiting for OpenWrt...")
    deadline = time.time() + 240
    while time.time() < deadline:
        try:
            raw3 = http("GET", "/", timeout=4)
            _, b = split_http(raw3)
            if b"Breed" in raw3:
                print("still breed")
            elif b"LuCI" in b or b"OpenWrt" in b or b"luci" in b:
                print("OPENWRT_HTTP")
                return 0
            else:
                print("other http", b[:60])
        except OSError:
            print("http down (rebooting?)")
        # SSH probe
        for host in (HOST, "192.168.10.1"):
            s = socket.socket()
            s.settimeout(2)
            try:
                s.bind((LOCAL, 0))
                s.connect((host, 22))
                ban = s.recv(64)
                if ban.startswith(b"SSH-"):
                    print(f"OPENWRT_SSH {host} {ban!r}")
                    return 0
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(5)
    print("TIMEOUT still not openwrt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
