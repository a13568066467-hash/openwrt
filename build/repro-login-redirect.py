#!/usr/bin/env python3
"""Reproduce home.me → /login → FAS redirect chain (from PC / via router)."""
from __future__ import annotations

import socket
import urllib.request
import os

import paramiko

PASS = os.environ["NDS_ROUTER_PASSWORD"]


def http_get(url: str, timeout: float = 8) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read(2000)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(2000)


def main() -> int:
    print("=== PC direct to cloud FAS ===")
    for url in (
        "http://192.168.1.125:8080/fas",
        "http://192.168.1.125:8080/portal/",
    ):
        try:
            code, hdrs, body = http_get(url)
            print(url, code, body[:80])
        except Exception as e:
            print(url, "ERR", e)

    print("\n=== via router: simulate opennds login redirect ===")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(os.environ.get("NDS_ROUTER_HOST", "192.168.1.1"), username="root", password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    cmd = r"""
set +e
# What /login returns for this client-ish request
echo '--- GET :2050/login ---'
curl -sS -D - -o /tmp/login.body -m 5 'http://127.0.0.1:2050/login' | head -40
echo BODY_HEAD:
head -c 400 /tmp/login.body; echo
echo
echo '--- GET home.me/login from br-guest src ---'
# bind-ish: curl from router to gateway address
curl -sS -D - -o /tmp/hlogin.body -m 5 -H 'Host: home.me' 'http://192.168.100.1:2050/login' | head -40
echo BODY_HEAD:
head -c 500 /tmp/hlogin.body; echo
echo
echo '--- extract Location ---'
grep -i '^Location:' /tmp/login.body /tmp/hlogin.body 2>/dev/null
# follow headers only for Location in -D dumps are in stdout above; re-fetch with -w
LOC=$(curl -sS -o /dev/null -w '%{redirect_url}' -m 5 'http://192.168.100.1:2050/login')
echo LOC="$LOC"
if [ -n "$LOC" ]; then
  echo '--- follow Location (max 3 hops, show final) ---'
  curl -sS -L --max-redirs 3 -D - -o /tmp/fas.body -m 8 "$LOC" | head -50
  echo FAS_BODY:
  head -c 600 /tmp/fas.body; echo
fi
echo
echo '--- can guest reach cloud? use nft counters before/after ---'
curl -sS -o /dev/null -w 'from_router_fas=%{http_code} time=%{time_total}\n' -m 5 'http://192.168.1.125:8080/fas'
# Try wget as source IP of phone if possible (may fail)
ip route get 192.168.1.125 from 192.168.100.132 2>&1 | head -3
"""
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR", err[:600])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
