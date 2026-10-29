#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "192.168.1.1",
    username="root",
    password="1234567890",
    timeout=8,
    allow_agent=False,
    look_for_keys=False,
)
cmd = r"""
echo "=== fas target ==="
uci -q get opennds.@opennds[0].fasremoteip
uci -q get opennds.@opennds[0].fasport
echo "=== lan ==="
ip -4 addr show br-lan | awk '/inet /{print}'
echo "=== cloud health from router ==="
curl -s -o /dev/null -w 'health=%{http_code}\n' --connect-timeout 3 http://192.168.1.125:8080/health
echo "=== guest dhcp ==="
uci -q get dhcp.guest.dhcp_option
ip -4 addr show br-guest 2>/dev/null | awk '/inet /{print}'
ip link show br-guest 2>/dev/null | head -1
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode())
err = e.read().decode()
if err.strip():
    print("STDERR:", err)
c.close()
