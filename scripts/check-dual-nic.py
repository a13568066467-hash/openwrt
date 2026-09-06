#!/usr/bin/env python3
import paramiko
import socket
import urllib.request

CLOUD = "192.168.1.125"
ROUTER = "192.168.1.1"


def tcp(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "OK"
    except Exception as e:
        return f"FAIL ({e})"


def http(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return f"{r.status}"
    except Exception as e:
        return f"FAIL ({e})"


print("=== PC -> services (via LAN IP) ===")
for port in (22, 8080, 8443, 3000, 3001):
    host = ROUTER if port == 22 else CLOUD
    print(f"  {host}:{port}  {tcp(host, port)}")

print("=== HTTP probes ===")
for url in (
    f"http://{CLOUD}:8080/health",
    f"http://{CLOUD}:8080/fas",
    f"http://{CLOUD}:8080/portal/",
    f"http://{CLOUD}:3000/",
    f"http://{CLOUD}:3001/portal/",
):
    print(f"  {url}  {http(url)}")

print("=== Router SSH ===")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    ROUTER,
    username="root",
    password="1234567890",
    timeout=10,
    allow_agent=False,
    look_for_keys=False,
)
cmd = r"""
echo ssh=OK
echo -n 'opennds='; pidof opennds >/dev/null && echo UP || echo DOWN
echo -n 'br-lan='; ip -4 addr show br-lan 2>/dev/null | awk '/inet /{print $2; exit}'
echo -n 'br-guest='; ip -4 addr show br-guest 2>/dev/null | awk '/inet /{print $2; exit}'
echo -n 'wan_up='; ubus call network.interface.wan status 2>/dev/null | jsonfilter -e '@.up'
echo -n 'wan_ip='; ubus call network.interface.wan status 2>/dev/null | jsonfilter -e '@["ipv4-address"][0].address'
echo -n 'fas='; uci get opennds.@opennds[0].fasremoteip
echo -n ':'; uci get opennds.@opennds[0].fasport; echo
echo -n 'fw_ports='; uci get firewall.allow_cloud_guest.dest_port 2>/dev/null; echo
curl -s -o /dev/null -w 'router->cloud health=%{http_code} fas=%{http_code} portal=%{http_code}\n' http://192.168.1.125:8080/health
curl -s -o /dev/null -w 'router->admin=%{http_code} userdev=%{http_code}\n' http://192.168.1.125:3000/
curl -s -o /dev/null -w 'x' http://192.168.1.125:3001/portal/ >/dev/null
curl -s -o /dev/null -w 'router->userdev=%{http_code}\n' http://192.168.1.125:3001/portal/
ndsctl status 2>/dev/null | grep -E 'FAS:|Managed|listening' || true
"""
_, stdout, stderr = client.exec_command(cmd, timeout=40)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
client.close()
