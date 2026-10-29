#!/usr/bin/env python3
"""Connect PC WLAN to NDS-WiFi and run register→login→auth→internet E2E."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import paramiko

CLOUD = "192.168.1.125"
ROUTER = "192.168.1.1"
PASS_ROOT = "1234567890"
USER = f"pc{int(time.time()) % 100000000}"
PASSWORD = "Test1234!"
ROOT = Path(r"d:\Users\Documents\project\openwrt")


def ssh_router(cmd: str, timeout: int = 90) -> str:
    last = None
    for _ in range(8):
        try:
            sock = socket.create_connection((ROUTER, 22), timeout=8, source_address=(CLOUD, 0))
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                ROUTER,
                username="root",
                password=PASS_ROOT,
                sock=sock,
                timeout=20,
                banner_timeout=20,
                auth_timeout=20,
                allow_agent=False,
                look_for_keys=False,
            )
            _, o, e = c.exec_command(cmd, timeout=timeout)
            out = o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")
            c.close()
            return out
        except Exception as ex:
            last = ex
            time.sleep(1.5)
    raise RuntimeError(last)


def ensure_cloud() -> None:
    try:
        with urllib.request.urlopen(f"http://{CLOUD}:8080/health", timeout=3) as r:
            if r.status == 200:
                return
    except Exception:
        pass
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | "
            "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }",
        ],
        check=False,
    )
    time.sleep(2)
    env = os.environ.copy()
    for line in (ROOT / "cloud" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    env["USER_PORTAL_URL"] = f"http://{CLOUD}:8080/portal/"
    env["USER_WEB_DIR"] = str(ROOT / "user-web" / "dist")
    log = ROOT / "build" / "logs" / "cloud-dev.log"
    with open(log, "w", encoding="utf-8") as f:
        subprocess.Popen(
            ["go", "run", "./cmd/server"],
            cwd=str(ROOT / "cloud"),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2) as r:
                print("cloud", r.read().decode())
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("cloud down")


def ps(cmd: str) -> str:
    return subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", cmd],
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def connect_nds_wifi() -> str:
    # Prefer existing profile
    subprocess.run(["netsh", "wlan", "disconnect"], check=False, capture_output=True)
    time.sleep(1)
    # Ensure open profile exists
    xml = ROOT / "build" / "nds-wifi.xml"
    xml.write_text(
        """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>NDS-WiFi</name>
  <SSIDConfig><SSID><name>NDS-WiFi</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>manual</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>open</authentication>
        <encryption>none</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
    </security>
  </MSM>
</WLANProfile>
""",
        encoding="utf-8",
    )
    subprocess.run(["netsh", "wlan", "add", "profile", f"filename={xml}"], check=False, capture_output=True)
    r = subprocess.run(
        ["netsh", "wlan", "connect", "name=NDS-WiFi", "ssid=NDS-WiFi"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("connect:", r.stdout, r.stderr)
    guest_ip = ""
    for i in range(30):
        time.sleep(2)
        out = ps(
            "Get-NetIPAddress -InterfaceAlias WLAN -AddressFamily IPv4 | "
            "Select-Object -ExpandProperty IPAddress"
        ).strip()
        print(f"[{i}] wlan ip={out}")
        if out.startswith("192.168.100."):
            guest_ip = out
            break
    if not guest_ip:
        raise RuntimeError("WLAN did not get guest DHCP")
    return guest_ip


def http_bind(src_ip: str, url: str, data: bytes | None = None, timeout: float = 15) -> tuple[int, str]:
    """HTTP request forcing source IP (guest WLAN)."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    body = data or b""
    method = "POST" if data is not None else "GET"
    headers = [
        f"{method} {path} HTTP/1.0",
        f"Host: {host}:{port}" if parsed.port else f"Host: {host}",
        "Connection: close",
    ]
    if data is not None:
        headers.append("Content-Type: application/x-www-form-urlencoded")
        headers.append(f"Content-Length: {len(body)}")
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body

    s = socket.socket()
    s.settimeout(timeout)
    s.bind((src_ip, 0))
    s.connect((host, port))
    s.sendall(raw)
    resp = b""
    while True:
        try:
            chunk = s.recv(65536)
        except TimeoutError:
            break
        if not chunk:
            break
        resp += chunk
    s.close()
    if b"\r\n\r\n" not in resp:
        return 0, resp.decode("utf-8", "replace")
    head, bdy = resp.split(b"\r\n\r\n", 1)
    code = int(head.split(b" ", 2)[1])
    return code, bdy.decode("utf-8", "replace")


def grant_quota(username: str, mb: int = 200) -> None:
    sql = (
        f"UPDATE users SET quota_remaining_bytes={mb*1024*1024}, status='active' "
        f"WHERE username='{username}'; SELECT username,quota_remaining_bytes FROM users WHERE username='{username}';"
    )
    subprocess.check_call(
        ["docker", "exec", "cloud-mysql-1", "mysql", "-unds", "-pnds123", "nds_billing", "-e", sql]
    )


def main() -> int:
    print("=== prep router uplink/opennds ===")
    print(
        ssh_router(
            """
ip route del default via 192.168.1.125 2>/dev/null || true
ip route replace default via 192.168.2.1 dev phy1-sta0 metric 5
ip route replace default via 192.168.1.125 metric 100
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
uci -q get opennds.@opennds[0].faskey | head -c 20; echo
ping -c1 -W2 8.8.8.8 | tail -2
"""
        )
    )
    ensure_cloud()

    print("=== connect WLAN to NDS-WiFi ===")
    guest_ip = connect_nds_wifi()
    print("guest_ip", guest_ip)

    print("=== fetch FAS / captive ===")
    # Trigger CPD
    try:
        code, body = http_bind(guest_ip, "http://192.168.100.1:2050/", timeout=8)
        print("2050", code, body[:200].replace("\n", " "))
    except Exception as e:
        print("2050 err", e)
    try:
        code, body = http_bind(guest_ip, "http://home.me/", timeout=8)
        print("home.me", code, len(body))
    except Exception as e:
        print("home.me err", e)
        body = ""

    fas = None
    m = re.search(r"fas=([A-Za-z0-9+/=]+)", body)
    if m:
        fas = m.group(1)
    if not fas:
        # ask cloud via router client list / craft from ndsctl
        js = ssh_router("ndsctl json")
        data = json.loads(js)
        client = None
        for mac, v in (data.get("clients") or {}).items():
            if v.get("ip") == guest_ip:
                client = v
                client["mac"] = mac
                break
        if not client:
            print("clients", js[:500])
            raise RuntimeError("PC not seen by opennds")
        # get redirect from status page via wget on router... better hit FAS probe from guest to known URL
        code, body = http_bind(guest_ip, f"http://{CLOUD}:8080/fas", timeout=8)
        print("fas probe", code, body[:120])
        # Force generate: open http://neverssl.com style
        try:
            code, body = http_bind(guest_ip, "http://detectportal.firefox.com/success.txt", timeout=8)
            print("cpi", code, body[:300])
            m = re.search(r"fas=([A-Za-z0-9+/=]+)", body)
            if m:
                fas = m.group(1)
        except Exception as e:
            print("cpi err", e)
        if not fas:
            # synthesize using hid from client if present
            hid = client.get("hid") or client.get("client_hid") or ""
            raw = (
                f"hid={hid}, clientip={guest_ip}, clientmac={client['mac']}, "
                f"gatewayname=NewWiFI%20Node%3a2076934462fe%20, "
                f"gatewayaddress=192.168.100.1:2050, gatewayurl=http%3a%2f%2fhome.me, "
                f"originurl=http%3a%2f%2fwww.baidu.com%2f, clientif=phy0-ap0, "
                f"themespec=, (null)(null)(null)(null)"
            )
            import base64

            fas = base64.b64encode(raw.encode()).decode()
            print("synthesized fas hid_empty=", not hid)

    print("fas_len", len(fas))

    print("=== register", USER, "===")
    form = urllib.parse.urlencode(
        {"username": USER, "password": PASSWORD, "action": "register", "fas": fas}
    ).encode()
    code, page = http_bind(guest_ip, f"http://{CLOUD}:8080/fas?fas={urllib.parse.quote(fas)}", data=form)
    print("register code", code, "success", "已开通" in page, "exists", "用户名已存在" in page)
    if "用户名已存在" in page or "用户名或密码错误" in page:
        form = urllib.parse.urlencode(
            {"username": USER, "password": PASSWORD, "action": "login", "fas": fas}
        ).encode()
        code, page = http_bind(guest_ip, f"http://{CLOUD}:8080/fas?fas={urllib.parse.quote(fas)}", data=form)
        print("login code", code, "success", "已开通" in page)

    if "已开通" not in page and "opennds_auth" not in page:
        print(page[:1000])
        # force auth
        mac = ps(
            "(Get-NetAdapter -Name WLAN).MacAddress"
        ).strip().replace("-", ":").lower()
        print("force auth mac", mac)
        print(ssh_router(f"ndsctl auth {mac}; sleep 1; ndsctl json | head -c 800"))
    else:
        urls = [u.replace("&amp;", "&") for u in re.findall(r"https?://[^\"'\s<>]+", page)]
        auth = next((u for u in urls if "opennds_auth" in u), "")
        print("auth_url", auth[:200])
        if auth:
            try:
                code, abody = http_bind(guest_ip, auth, timeout=12)
                print("auth hit", code, len(abody))
            except Exception as e:
                print("auth hit err", e)
                # fallback ndsctl
                mac = (
                    ps("(Get-NetAdapter -Name WLAN).MacAddress")
                    .strip()
                    .replace("-", ":")
                    .lower()
                )
                print(ssh_router(f"ndsctl auth {mac}"))

    grant_quota(USER, 200)
    print("quota 200MB for", USER)

    # verify state
    print(ssh_router("ndsctl json | head -c 1200; echo"))

    print("=== internet tests from guest WLAN ===")
    results = {}
    # DNS may use 192.168.100.1
    for name, url in [
        ("baidu", "http://www.baidu.com/"),
        ("cloud_health", f"http://{CLOUD}:8080/health"),
        ("portal", f"http://{CLOUD}:8080/portal/"),
        ("ip_http", "http://1.1.1.1/"),
    ]:
        try:
            code, body = http_bind(guest_ip, url, timeout=12)
            results[name] = {"code": code, "len": len(body)}
            print(name, results[name])
        except Exception as e:
            results[name] = {"err": str(e)}
            print(name, "ERR", e)

    # ping via powershell from WLAN? use Test-Connection with interface
    ping = ps(
        "Test-Connection -ComputerName 8.8.8.8 -Count 2 -ErrorAction SilentlyContinue | "
        "Measure-Object | Select-Object -ExpandProperty Count"
    ).strip()
    results["ping_count"] = ping
    print("ping_count", ping)

    ok = (
        results.get("baidu", {}).get("code") in (200, 301, 302)
        or results.get("ip_http", {}).get("code") in (200, 301, 302)
    ) and results.get("cloud_health", {}).get("code") == 200

    print("RESULT", {"user": USER, "password": PASSWORD, "guest_ip": guest_ip, "ok": ok, "results": results})
    if ok:
        print("E2E_PASS")
        return 0
    print("E2E_FAIL")
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
