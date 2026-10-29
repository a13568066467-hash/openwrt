#!/usr/bin/env python3
import paramiko
import time

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
# ensure guest up first
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
sleep 2
# align FAS level with cloud authmon path if needed
uci set opennds.@opennds[0].fas_secure_enabled='1'
uci commit opennds
/etc/init.d/opennds stop 2>/dev/null || true
sleep 1
/etc/init.d/opennds start
sleep 3
pgrep -x opennds >/dev/null && echo opennds=UP || echo opennds=DOWN
echo "fas=$(uci -q get opennds.@opennds[0].fasremoteip):$(uci -q get opennds.@opennds[0].fasport)"
echo "secure=$(uci -q get opennds.@opennds[0].fas_secure_enabled)"
echo "faskey=$(uci -q get opennds.@opennds[0].faskey | head -c 12)..."
echo "gw=$(uci -q get opennds.@opennds[0].gatewayname)"
ndsctl status 2>/dev/null | head -20
# firewall allow to cloud
nft list ruleset 2>/dev/null | grep -E '192.168.1.125|8080|allow_cloud' | head -20 || iptables -S 2>/dev/null | grep -E '125|8080' | head -20
"""
_, o, e = c.exec_command(cmd, timeout=90)
print(o.read().decode())
err = e.read().decode()
if err.strip():
    print("STDERR", err[-1500:])
c.close()
