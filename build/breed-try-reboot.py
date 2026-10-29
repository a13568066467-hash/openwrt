#!/usr/bin/env python3
"""If still Breed after 100% flash, try reboot endpoint."""
from __future__ import annotations

import socket
import time

LOCAL = "192.168.1.125"
HOST = "192.168.1.1"


def http(method: str, path: str, body: bytes = b"", timeout: float = 10) -> bytes:
    headers = [f"{method} {path} HTTP/1.0", f"Host: {HOST}", "Connection: close"]
    if method == "POST":
        headers.append(f"Content-Length: {len(body)}")
        headers.append("Content-Type: application/x-www-form-urlencoded")
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


def identify() -> str:
    try:
        raw = http("GET", "/")
        if b"Breed" in raw:
            return "breed"
        if b"LuCI" in raw or b"OpenWrt" in raw or b"luci" in raw:
            return "openwrt"
        return "other"
    except OSError:
        return "down"


def main() -> None:
    mode = identify()
    print("initial=", mode)
    if mode == "openwrt":
        return
    if mode == "breed":
        for path in ("/reboot", "/reboot.html", "/reset.html", "/cgi-bin/reboot"):
            try:
                raw = http("GET", path, timeout=5)
                print(path, "GET", raw[:120])
            except OSError as e:
                print(path, "GET fail", e)
            try:
                raw = http("POST", path, b"", timeout=5)
                print(path, "POST", raw[:120])
            except OSError as e:
                print(path, "POST fail", e)
        # common Breed: RequestURL('/reboot.html') or link in menu
        print("after reboot trigger, waiting...")
        time.sleep(15)
        for i in range(40):
            m = identify()
            print(f"try {i+1} {m}")
            if m == "openwrt":
                # check ssh
                s = socket.socket()
                s.settimeout(3)
                try:
                    s.bind((LOCAL, 0))
                    s.connect((HOST, 22))
                    print("SSH", s.recv(40))
                except OSError as e:
                    print("no ssh yet", e)
                finally:
                    s.close()
                return
            if m == "down":
                print("down (rebooting?)")
            time.sleep(5)
    print("final=", identify())


if __name__ == "__main__":
    main()
