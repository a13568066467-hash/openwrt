#!/usr/bin/env python3
import paramiko

SCRIPT = r"""
echo '=== br-lan ==='
ip -4 addr show br-lan | grep inet
echo '=== wan device ==='
ip -4 addr show wan 2>/dev/null | grep inet || ip -4 addr show eth0.2 2>/dev/null | grep inet || true
ubus call network.interface.wan status
echo
echo '=== routes ==='
ip route
echo '=== uci network lan/wan ==='
uci show network.lan
uci show network.wan
echo '=== ping upstream via wan ==='
ping -c 2 -W 2 -I wan 8.8.8.8 2>&1 | tail -5
ping -c 1 -W 2 192.168.1.1 2>&1 | tail -3
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "192.168.1.1",
    username="root",
    password="1234567890",
    timeout=10,
    allow_agent=False,
    look_for_keys=False,
)
stdin, stdout, stderr = c.exec_command(SCRIPT, timeout=40)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err[-1000:])
c.close()
