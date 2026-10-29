#!/usr/bin/env python3
"""Set OpenWrt root password after fresh flash (empty password)."""
import os
import paramiko

HOST = os.environ.get("NDS_ROUTER_HOST", "192.168.1.1")
NEW_PASS = os.environ["NDS_ROUTER_PASSWORD"]


def try_connect(password: str) -> paramiko.SSHClient | None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(
            HOST,
            username="root",
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
            auth_timeout=10,
        )
        return c
    except Exception as e:
        print(f"auth fail password={password!r}: {e}")
        return None


def main() -> int:
    # Fresh flash: empty password; already configured: lab password
    for pw in ("", NEW_PASS):
        c = try_connect(pw)
        if c:
            print(f"connected with password={pw!r}")
            if pw != NEW_PASS:
                _, o, e = c.exec_command(
                    f"echo -e '{NEW_PASS}\\n{NEW_PASS}' | passwd root"
                )
                out = o.read().decode() + e.read().decode()
                print("passwd:", out.strip())
            _, o, _ = c.exec_command(
                "cat /etc/openwrt_release; uname -a; "
                "opkg list-installed 2>/dev/null | grep -E 'opennds|nds-' || true"
            )
            print(o.read().decode())
            c.close()
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
