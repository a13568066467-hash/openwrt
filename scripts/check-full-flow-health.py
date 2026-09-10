#!/usr/bin/env python3
"""End-to-end health gate for the NewWiFI/openNDS billing flow.

This script verifies the pieces that previously caused false positives: a port
listening with the wrong database, an agent running in local-only mode, router
defaults that differ from the working field configuration, and a portal login
path that authenticates but fails to hand the browser into the user center.
"""

from __future__ import annotations

import json
import hashlib
import os
import sys
import time
import warnings
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

warnings.filterwarnings("ignore", message=".*Blowfish has been deprecated.*")

import paramiko
import pymysql


CLOUD_IP = os.environ.get("NDS_CLOUD_IP", "192.168.1.125")
CLOUD_DIR = Path(__file__).resolve().parents[1] / "cloud"


def load_cloud_env() -> dict[str, str]:
    path = CLOUD_DIR / ".env"
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


DOTENV = load_cloud_env()
CLOUD_PORT = int(os.environ.get("NDS_CLOUD_PORT", "8080"))
CLOUD_BASE = os.environ.get("NDS_CLOUD_BASE", f"http://{CLOUD_IP}:{CLOUD_PORT}")
CLOUD_HEALTH = f"{CLOUD_BASE}/health"
FAS_KEY = os.environ.get("NDS_FAS_KEY") or DOTENV.get("FAS_KEY", "nds-billing-fas-key")
AUTH_LOG_PATH = os.environ.get("NDS_AUTH_LOG_PATH") or DOTENV.get("AUTH_LOG_PATH", "./data/auth_queue")
AUTH_LOG_DIR = Path(AUTH_LOG_PATH)
if not AUTH_LOG_DIR.is_absolute():
    AUTH_LOG_DIR = CLOUD_DIR / AUTH_LOG_DIR
MYSQL = {
    "host": os.environ.get("NDS_MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("NDS_MYSQL_PORT", "3307")),
    "user": os.environ.get("NDS_MYSQL_USER", "nds"),
    "password": os.environ.get("NDS_MYSQL_PASSWORD", "nds123"),
    "database": os.environ.get("NDS_MYSQL_DATABASE", "nds_billing"),
    "charset": "utf8mb4",
}
ROUTER_IP = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
ROUTER_PASSWORD = os.environ.get("NDS_ROUTER_PASSWORD") or os.environ.get("NDS_ROUTER_PASS", "1234567890")
DEVICE_ID = os.environ.get("NDS_DEVICE_ID", "NewWiFI")
DEVICE_SECRET = os.environ.get("NDS_DEVICE_SECRET", "nds-newifi-secret-16chars")
TEST_USERNAME = os.environ.get("NDS_TEST_USERNAME", "13568066467")
TEST_PASSWORD = os.environ.get("NDS_TEST_PASSWORD", "123456")
TEST_USER_ID = int(os.environ.get("NDS_TEST_USER_ID", "8"))
TEST_CLIENT_MAC = os.environ.get("NDS_TEST_CLIENT_MAC", "ee:13:8c:d1:62:98")
HEALTH_USERNAME = os.environ.get("NDS_HEALTH_USERNAME", "__nds_healthcheck__")
HEALTH_PASSWORD = os.environ.get("NDS_HEALTH_PASSWORD", "healthcheck-password-123456")
HEALTH_CLIENT_IP = os.environ.get("NDS_HEALTH_CLIENT_IP", "192.168.100.250")
HEALTH_CLIENT_MAC = os.environ.get("NDS_HEALTH_CLIENT_MAC", "02:00:00:00:00:81")
HEALTH_CLIENT_HID = os.environ.get("NDS_HEALTH_CLIENT_HID", "healthhid")


failures: list[str] = []
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}{': ' + detail if detail else ''}")
    if not ok:
        failures.append(name if not detail else f"{name}: {detail}")


def http_json(url: str, method: str = "GET", body: bytes | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with NO_PROXY_OPENER.open(req, timeout=5) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(data or "{}")
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(data or "{}")
        except json.JSONDecodeError:
            payload = {"body": data}
        return exc.code, payload


def http_text(
    url: str,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with NO_PROXY_OPENER.open(req, timeout=5) as resp:
            return resp.status, dict(resp.headers.items()), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read().decode("utf-8", errors="replace")


def ssh_router(command: str) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        ROUTER_IP,
        username="root",
        password=ROUTER_PASSWORD,
        look_for_keys=False,
        allow_agent=False,
        timeout=10,
    )
    try:
        _, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return out + err
    finally:
        client.close()


def read_opennds_client(mac: str) -> dict | None:
    data = None
    last_raw = ""
    for attempt in range(10):
        raw = ssh_router("ndsctl json 2>/dev/null || true")
        last_raw = raw
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            raw = raw[start : end + 1]
        try:
            data = json.loads(raw or "{}")
            break
        except json.JSONDecodeError:
            if attempt < 9:
                time.sleep(1.5)
                continue
    if data is None:
        check("openNDS client json", False, "invalid ndsctl json: " + last_raw[:200].replace("\n", "\\n"))
        return None

    clients = data.get("clients") or {}
    client = clients.get(mac.lower())
    if not client:
        return None
    return client


def user_login(username: str, password: str) -> tuple[int, dict]:
    body = json.dumps({"username": username, "password": password}).encode()
    return http_json(f"{CLOUD_BASE}/api/v1/user/login", "POST", body)


def ensure_health_user() -> bool:
    status, payload = user_login(HEALTH_USERNAME, HEALTH_PASSWORD)
    if status == 200 and payload.get("token"):
        return True

    body = json.dumps({"username": HEALTH_USERNAME, "password": HEALTH_PASSWORD}).encode()
    reg_status, _ = http_json(f"{CLOUD_BASE}/api/v1/user/register", "POST", body)
    if reg_status not in (200, 409):
        check("health user provision", False, f"status={reg_status}")
        return False

    status, payload = user_login(HEALTH_USERNAME, HEALTH_PASSWORD)
    ok = status == 200 and bool(payload.get("token"))
    check("health user login", ok, f"status={status}")
    return ok


def cleanup_health_probe(cur) -> None:
    cur.execute(
        "UPDATE sessions s JOIN users u ON u.id=s.user_id "
        "SET s.active=0, s.ended_at=NOW() "
        "WHERE u.username=%s AND s.mac=%s AND s.active=1",
        (HEALTH_USERNAME, HEALTH_CLIENT_MAC.lower()),
    )
    closed = cur.rowcount
    cur.execute(
        "DELETE ud FROM user_devices ud JOIN users u ON u.id=ud.user_id "
        "WHERE u.username=%s AND ud.mac=%s",
        (HEALTH_USERNAME, HEALTH_CLIENT_MAC.lower()),
    )
    check("health probe cleanup", True, f"closed_sessions={closed} deleted_devices={cur.rowcount}")


def cleanup_health_auth_queue() -> None:
    gateway = DEVICE_ID
    if "%" not in gateway:
        gateway = urllib.parse.quote_plus(gateway)
        gateway = gateway.replace("%3A", "%3a").replace("%2F", "%2f")
    gateway_hash = hashlib.sha256(gateway.encode()).hexdigest()
    rhid = hashlib.sha256((HEALTH_CLIENT_HID.strip() + FAS_KEY.strip()).encode()).hexdigest()
    target = AUTH_LOG_DIR / gateway_hash / rhid
    removed = 0
    try:
        target.unlink()
        removed = 1
    except FileNotFoundError:
        pass
    try:
        target.parent.rmdir()
    except OSError:
        pass
    check("health auth queue cleanup", True, f"removed_files={removed}")


def main() -> int:
    status, health = http_json(CLOUD_HEALTH)
    check("cloud /health", status == 200 and health.get("status") == "ok", str(health))
    db_target = str(health.get("database_target", ""))
    check(
        "cloud database target",
        f":{MYSQL['port']}" in db_target and f"/{MYSQL['database']}" in db_target,
        db_target,
    )
    check("cloud portal url", health.get("user_portal_url") == f"{CLOUD_BASE}/portal/", str(health.get("user_portal_url", "")))

    reg_body = json.dumps({"device_id": "health-probe", "name": "probe", "secret": "health-probe-secret"}).encode()
    reg_status, _ = http_json(f"{CLOUD_BASE}/api/v1/device/register", "POST", reg_body)
    check("device register protected", reg_status == 403, f"status={reg_status}")

    login_status, login_payload = user_login(TEST_USERNAME, TEST_PASSWORD)
    token = str(login_payload.get("token", ""))
    check("user api login", login_status == 200 and token != "", f"status={login_status}")
    if token:
        profile_req = urllib.request.Request(f"{CLOUD_BASE}/api/v1/user/profile")
        profile_req.add_header("Authorization", f"Bearer {token}")
        try:
            with NO_PROXY_OPENER.open(profile_req, timeout=5) as resp:
                profile = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                profile_status = resp.status
        except urllib.error.HTTPError as exc:
            profile = {"body": exc.read().decode("utf-8", errors="replace")}
            profile_status = exc.code
        check(
            "user center profile",
            profile_status == 200 and profile.get("username") == TEST_USERNAME,
            f"status={profile_status} username={profile.get('username')}",
        )

    if ensure_health_user():
        fas_raw = ",".join(
            [
                f"clientip={HEALTH_CLIENT_IP}",
                f"clientmac={HEALTH_CLIENT_MAC}",
                f"gatewayname={DEVICE_ID}",
                "gatewayaddress=192.168.100.1",
                "authdir=/opennds_auth/",
                f"client_hid={HEALTH_CLIENT_HID}",
                "originurl=http://example.com/",
                "clientif=br-guest",
            ]
        )
        fas_encoded = urllib.parse.quote(
            __import__("base64").b64encode(fas_raw.encode()).decode(),
            safe="",
        )
        form = urllib.parse.urlencode(
            {
                "fas": fas_encoded,
                "action": "login",
                "username": HEALTH_USERNAME,
                "password": HEALTH_PASSWORD,
            }
        ).encode()
        fas_status, _, fas_body = http_text(
            f"{CLOUD_BASE}/fas?fas={fas_encoded}",
            "POST",
            form,
            "application/x-www-form-urlencoded",
        )
        fas_decoded_body = urllib.parse.unquote(fas_body)
        check("fas login accepted", fas_status == 200 and "已开通" in fas_body, f"status={fas_status}")
        check("fas gateway auth redirect", "/opennds_auth/" in fas_decoded_body and "redir=" in fas_decoded_body)
        check("fas user center token redirect", "/portal/" in fas_decoded_body and "token=" in fas_decoded_body)
        cleanup_health_auth_queue()

        token_status, token_payload = user_login(HEALTH_USERNAME, HEALTH_PASSWORD)
        health_token = str(token_payload.get("token", ""))
        token_form = urllib.parse.urlencode(
            {
                "fas": fas_encoded,
                "action": "token",
                "token": health_token,
            }
        ).encode()
        token_fas_status, _, token_fas_body = http_text(
            f"{CLOUD_BASE}/fas?fas={fas_encoded}",
            "POST",
            token_form,
            "application/x-www-form-urlencoded",
        )
        token_fas_decoded_body = urllib.parse.unquote(token_fas_body)
        check("fas token login accepted", token_status == 200 and health_token != "" and token_fas_status == 200 and "已开通" in token_fas_body, f"login_status={token_status} fas_status={token_fas_status}")
        check("fas token gateway auth redirect", "/opennds_auth/" in token_fas_decoded_body and "redir=" in token_fas_decoded_body)
        check("fas token user center redirect", "/portal/" in token_fas_decoded_body and "token=" in token_fas_decoded_body)
        cleanup_health_auth_queue()

    conn = pymysql.connect(**MYSQL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, online, last_heartbeat FROM routers WHERE device_id=%s", (DEVICE_ID,))
        router = cur.fetchone()
        check("router registered in db", router is not None, str(router))
        if router:
            check("router heartbeat online", bool(router[1]), str(router))

        cur.execute("SELECT id, quota_remaining_bytes, status FROM users WHERE username=%s", (TEST_USERNAME,))
        user = cur.fetchone()
        check("known test user exists", user is not None, str(user))
        if user:
            check("known test user active", user[2] == "active", str(user))

        cur.execute(
            "SELECT upload_bytes, download_bytes, active FROM sessions "
            "WHERE user_id=%s ORDER BY id DESC LIMIT 1",
            (TEST_USER_ID,),
        )
        session = cur.fetchone()
        check("latest user session exists", session is not None, str(session))
        cur.execute(
            "SELECT COALESCE(MAX(upload_bytes + download_bytes), 0) FROM sessions "
            "WHERE user_id=%s",
            (TEST_USER_ID,),
        )
        metered = cur.fetchone()
        check("user has metered session", int((metered or [0])[0] or 0) > 0, str(metered))

        live_client = read_opennds_client(TEST_CLIENT_MAC)
        check("test phone live in openNDS", live_client is not None, TEST_CLIENT_MAC)
        if live_client:
            token_value = str(live_client.get("token") or "")
            session_start = str(live_client.get("session_start") or "")
            session_key = f"{DEVICE_ID}:{TEST_CLIENT_MAC.lower()}:{token_value}:{session_start}"
            live_total = (
                int(live_client.get("download_this_session") or 0)
                + int(live_client.get("upload_this_session") or 0)
            ) * 1024
            cur.execute(
                "SELECT COALESCE(MAX(total_bytes), 0) FROM usage_records WHERE session_key=%s",
                (session_key,),
            )
            recorded_total = int((cur.fetchone() or [0])[0] or 0)
            check(
                "live openNDS session metered",
                live_total == 0 or recorded_total >= live_total,
                f"live={live_total} recorded={recorded_total} key={session_key}",
            )
            cur.execute(
                "SELECT COALESCE(MAX(upload_bytes + download_bytes), 0) FROM sessions "
                "WHERE user_id=%s AND mac=%s AND active=1",
                (TEST_USER_ID, TEST_CLIENT_MAC.lower()),
            )
            active_total = int((cur.fetchone() or [0])[0] or 0)
            check(
                "active session reflects live counters",
                live_total == 0 or active_total >= live_total,
                f"live={live_total} active={active_total}",
            )
        cleanup_health_probe(cur)
        conn.commit()
    finally:
        conn.close()

    router_out = ssh_router(
        r"""
echo opennds_enabled=$(/etc/init.d/opennds enabled >/dev/null 2>&1; echo $?)
echo agent_enabled=$(/etc/init.d/nds-agent enabled >/dev/null 2>&1; echo $?)
echo opennds_running=$(pgrep opennds >/dev/null 2>&1; echo $?)
echo agent_running=$(pgrep -f '/usr/lib/nds-agent/main.uc' >/dev/null 2>&1; echo $?)
uci -q get opennds.@opennds[0].fas_secure_enabled | sed 's/^/fas_secure_enabled=/'
uci -q get opennds.@opennds[0].fwhook_enabled | sed 's/^/fwhook_enabled=/'
uci -q get opennds.@opennds[0].gatewayname | sed 's/^/gatewayname=/'
uci -q get nds-agent.main.cloud_url | sed 's/^/agent_cloud_url=/'
uci -q get nds-agent.main.device_id | sed 's/^/agent_device_id=/'
uci -q get nds-agent.main.device_secret >/dev/null 2>&1 && echo agent_device_secret_present=1 || echo agent_device_secret_present=0
uci -q get nds-agent.main.report_interval | sed 's/^/agent_report_interval=/'
uci -q get firewall.guest_to_lan.dest | sed 's/^/guest_to_lan_dest=/'
uci -q get firewall.guest_to_lan_nat.target | sed 's/^/guest_nat_target=/'
"""
    )
    print("--- router ---")
    print(router_out.strip())
    check("router openNDS enabled", "opennds_enabled=0" in router_out)
    check("router agent enabled", "agent_enabled=0" in router_out)
    check("router openNDS running", "opennds_running=0" in router_out)
    check("router agent running", "agent_running=0" in router_out)
    check("router FAS level 1", "fas_secure_enabled=1" in router_out)
    check("router fwhook enabled", "fwhook_enabled=1" in router_out)
    check("router gateway name matches device id", f"gatewayname={DEVICE_ID}" in router_out)
    check("router agent cloud", f"agent_cloud_url={CLOUD_BASE}" in router_out)
    check("router agent device id", f"agent_device_id={DEVICE_ID}" in router_out)
    check("router agent secret present", "agent_device_secret_present=1" in router_out)
    check("router agent report interval", "agent_report_interval=30" in router_out)
    check("router guest to lan", "guest_to_lan_dest=lan" in router_out)
    check("router guest nat", "guest_nat_target=MASQUERADE" in router_out)

    if failures:
        print("--- failures ---")
        for failure in failures:
            print(failure)
        return 1

    print("FULL_FLOW_HEALTH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
