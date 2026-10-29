#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "192.168.1.1",
    username="root",
    password="1234567890",
    timeout=15,
    allow_agent=False,
    look_for_keys=False,
)
cmd = r"""
set -x
uci show network.guest
uci show network.guest_dev
uci show wireless.guest_radio0
echo '=== wifi ==='
wifi status 2>/dev/null | head -c 1200; echo
echo '=== ensure ==='
/usr/lib/nds-profile/ensure-guest-dhcp.sh; echo ensure_rc=$?
sleep 3
ip link show br-guest 2>&1 | head -2
ip -4 addr show br-guest 2>&1
ubus call network.interface.guest status 2>/dev/null | jsonfilter -e '@.up' -e '@.errors[0].code' -e '@.device'
iwinfo 2>/dev/null | head -40
ls /sys/class/net/
"""
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode())
err = e.read().decode()
if err.strip():
    print("STDERR", err[-2000:])
c.close()
