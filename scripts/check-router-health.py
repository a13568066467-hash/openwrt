#!/usr/bin/env python3
import paramiko

SCRIPT = r"""
echo '=== version ==='
. /etc/openwrt_release 2>/dev/null
echo "DISTRIB_DESCRIPTION=$DISTRIB_DESCRIPTION"
echo '=== processes ==='
pidof opennds >/dev/null && echo opennds=UP || echo opennds=DOWN
pidof dnsmasq >/dev/null && echo dnsmasq=UP || echo dnsmasq=DOWN
pgrep -f nds-agent >/dev/null && echo nds-agent=UP || echo nds-agent=DOWN
echo '=== br-guest ==='
ip -4 addr show br-guest 2>/dev/null | grep inet || echo 'NO_IP'
brctl show br-guest 2>/dev/null || true
echo '=== dhcp.guest uci ==='
uci show dhcp.guest 2>/dev/null || echo 'NO_dhcp.guest'
echo '=== dnsmasq dhcp-range ==='
grep dhcp-range /var/etc/dnsmasq.conf.* 2>/dev/null || echo 'NO_RANGE'
echo '=== leases ==='
wc -l /tmp/dhcp.leases 2>/dev/null
cat /tmp/dhcp.leases 2>/dev/null | head -8
echo '=== wifi ==='
iwinfo 2>/dev/null | grep -E 'ESSID|Access Point|Encryption' | head -12
echo '=== wan ==='
ubus call network.interface.wan status 2>/dev/null | jsonfilter -e '@.up'
echo '=== fas ==='
uci -q get opennds.@opennds[0].fasremoteip
uci -q get opennds.@opennds[0].fasport
echo '=== ndsctl ==='
ndsctl status 2>/dev/null | head -20
echo '=== clients ==='
ndsctl json 2>/dev/null | head -c 400; echo
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
    print("STDERR:", err[-800:])
c.close()
