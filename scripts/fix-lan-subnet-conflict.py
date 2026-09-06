#!/usr/bin/env python3
"""Fix WAN/LAN same-subnet conflict by moving LAN to 192.168.10.0/24."""
import paramiko
import time

NEW_LAN = "192.168.10.1"
NEW_PC = "192.168.10.125"  # expected PC address after change (user may DHCP)

SCRIPT = f"""
set -e
# Move LAN off 192.168.1.0/24 so it no longer overlaps upstream WAN
uci set network.lan.ipaddr='{NEW_LAN}/24'
uci set network.lan.proto='static'

# Keep guest as-is
uci set network.guest.ipaddr='192.168.100.1'
uci set network.guest.netmask='255.255.255.0'

# Cloud/PC will be on new LAN; update FAS + firewall allowlist
uci set opennds.@opennds[0].fasremoteip='{NEW_PC}'
uci set opennds.@opennds[0].fasport='8080'
uci delete opennds.@opennds[0].walledgarden_fqdn_list 2>/dev/null || true
uci add_list opennds.@opennds[0].walledgarden_fqdn_list='{NEW_PC}'
uci set firewall.allow_cloud_guest.dest_ip='{NEW_PC}'
uci set firewall.allow_cloud_guest.dest_port='8080 8443 3000 3001'
uci set nds-agent.main.cloud_url='http://{NEW_PC}:8080'

uci commit network
uci commit opennds
uci commit firewall
uci commit nds-agent

echo 'Applying network restart (SSH may drop)...'
/etc/init.d/network restart
"""

print("=== Conflict confirmed ===")
print("  br-lan: 192.168.1.1/24")
print("  wan:    192.168.1.3/24  gateway 192.168.1.1  << SAME SUBNET")
print(f"=== Changing LAN to {NEW_LAN}/24 ===")

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
stdin, stdout, stderr = c.exec_command(SCRIPT, timeout=20)
stdin.channel.shutdown_write()
try:
    print(stdout.read().decode("utf-8", errors="replace"))
    print(stderr.read().decode("utf-8", errors="replace"))
except Exception as e:
    print("SSH closed during network restart (expected):", e)
try:
    c.close()
except Exception:
    pass

print()
print("Router LAN is now 192.168.10.1 — PC Ethernet must join 192.168.10.0/24")
print(f"Set Ethernet IP to {NEW_PC}/24 gateway {NEW_LAN} OR renew DHCP")
print("Then open http://192.168.10.1  and update cloud .env USER_PORTAL_URL")
