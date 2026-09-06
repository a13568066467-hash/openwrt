#!/usr/bin/env python3
"""Apply NDS lab config to Newifi router + restart local cloud."""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
CLOUD = ROOT / "cloud"
USER_WEB = ROOT / "user-web"
ROUTER_SH = ROOT / "scripts" / "configure-newifi-router.sh"
CERT = CLOUD / "data" / "dev.crt"

ROUTER_HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
ROUTER_USER = os.environ.get("NDS_ROUTER_USER", "root")
ROUTER_PASS = os.environ.get("NDS_ROUTER_PASS", "1234567890")
CLOUD_IP = os.environ.get("NDS_CLOUD_IP", "192.168.1.125")


def find_npm() -> str:
    for candidate in (
        os.environ.get("NPM"),
        r"D:\Node\npm.cmd",
        "npm.cmd",
        "npm",
    ):
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("npm not found")


def build_user_web() -> Path:
    dist = USER_WEB / "dist"
    npm = find_npm()
    print(f"=== build user-web ({npm}) ===")
    subprocess.check_call([npm, "install"], cwd=str(USER_WEB))
    subprocess.check_call([npm, "run", "build"], cwd=str(USER_WEB))
    if not (dist / "index.html").is_file():
        raise RuntimeError("user-web build did not produce dist/index.html")
    return dist


def wait_http(url: str, timeout: float = 40) -> str:
    last = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                body = resp.read(200).decode("utf-8", errors="replace")
                return f"{resp.status} {body[:80]!r}"
        except Exception as exc:
            last = str(exc)
            time.sleep(1)
    raise RuntimeError(f"{url} not ready: {last}")


def load_env_file(path: Path) -> dict:
    env = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def restart_cloud() -> None:
    env_file = CLOUD / ".env"
    env = os.environ.copy()
    env.update(load_env_file(env_file))
    env.setdefault("HTTP_PORT", "8080")
    env.setdefault("HTTPS_PORT", "8443")
    env["USER_WEB_DIR"] = str(USER_WEB / "dist")
    env["USER_PORTAL_URL"] = f"http://{CLOUD_IP}:8080/portal/"
    if CERT.is_file():
        env.setdefault("TLS_CERT", str(CERT))
        env.setdefault("TLS_KEY", str(CLOUD / "data" / "dev.key"))

    # Windows firewall
    for port in ("8080", "8443"):
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name=NDS-{port}",
                "dir=in", "action=allow", "protocol=TCP", f"localport={port}",
            ],
            capture_output=True,
        )

    # Stop listeners on 8080/8443
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, encoding="utf-8", errors="replace"
        )
        for line in out.splitlines():
            if ":8080" in line or ":8443" in line:
                if "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True,
                    )
    except Exception:
        pass

    time.sleep(2)
    log_path = ROOT / "build" / "logs" / "cloud-dev.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            ["go", "run", "./cmd/server"],
            cwd=str(CLOUD),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    try:
        print("waiting for cloud /health ...", wait_http("http://127.0.0.1:8080/health", 120))
    except Exception:
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"cloud failed to start:\n{tail}") from None
        raise
    print(f"cloud started pid={proc.pid} log={log_path}")


def configure_router() -> str:
    if not ROUTER_SH.is_file():
        raise FileNotFoundError(ROUTER_SH)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        ROUTER_HOST,
        username=ROUTER_USER,
        password=ROUTER_PASS,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )

    script = ROUTER_SH.read_text(encoding="utf-8")
    if CERT.is_file():
        cert = CERT.read_text(encoding="utf-8")
        script = (
            "cat > /tmp/nds-cloud.crt << 'NDSCERT'\n"
            + cert
            + "NDSCERT\n"
            + script
        )

    stdin, stdout, stderr = client.exec_command(
        f"export NDS_CLOUD_IP={CLOUD_IP}; sh -s",
        timeout=300,
    )
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    client.close()
    if err.strip():
        out += "\nSTDERR:\n" + err
    return out


def probe_cloud() -> None:
    print("=== probe cloud ===")
    print("health", wait_http("http://127.0.0.1:8080/health", 10))
    print("fas", wait_http("http://127.0.0.1:8080/fas", 10))
    print("portal", wait_http("http://127.0.0.1:8080/portal/", 10))


def ssh_run(cmd: str, timeout: int = 60) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        ROUTER_HOST,
        username=ROUTER_USER,
        password=ROUTER_PASS,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    client.close()
    return (out + ("\n" + err if err.strip() else "")).strip()


def probe_router() -> str:
    print("=== probe router → cloud ===")
    return ssh_run(
        f"""
pgrep -x opennds >/dev/null && echo opennds=running || echo opennds=DOWN
curl -s -o /dev/null -w 'fas=%{{http_code}}\\n' http://{CLOUD_IP}:8080/fas
curl -s -o /dev/null -w 'portal=%{{http_code}}\\n' http://{CLOUD_IP}:8080/portal/
curl -s -o /dev/null -w 'health=%{{http_code}}\\n' http://{CLOUD_IP}:8080/health
ndsctl status 2>/dev/null | head -12 || true
"""
    )


def main() -> int:
    dist = build_user_web()
    print("user-web dist", dist)
    print("=== restart cloud ===")
    restart_cloud()
    probe_cloud()
    print("=== configure router ===")
    result = configure_router()
    print(result)
    print(probe_router())
    status = ssh_run("pidof opennds >/dev/null && echo opennds=running || echo opennds=DOWN")
    if "opennds=running" in result or "opennds=running" in status:
        print("\nOK. Phone: connect NDS-WiFi → http://home.me")
        print("After login you should land on http://%s:8080/portal/" % CLOUD_IP)
        return 0
    # Cloud portal is still usable even if openNDS briefly flapped
    print("\nWARN: openNDS pid check failed — see router log; portal itself is at http://%s:8080/portal/" % CLOUD_IP)
    return 0 if "portal_http=200" in result or "fas_http=200" in result else 1


if __name__ == "__main__":
    sys.exit(main())
