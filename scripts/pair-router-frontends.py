#!/usr/bin/env python3
import paramiko

SCRIPT = r"""
uci set firewall.allow_cloud_guest.dest_port='8080 8443 3000 3001'
uci delete opennds.@opennds[0].walledgarden_port_list
uci add_list opennds.@opennds[0].walledgarden_port_list='8080'
uci add_list opennds.@opennds[0].walledgarden_port_list='3000'
uci add_list opennds.@opennds[0].walledgarden_port_list='3001'
uci commit firewall
uci commit opennds
/etc/init.d/firewall reload
echo "ports=$(uci get firewall.allow_cloud_guest.dest_port)"
echo "wg=$(uci -q get opennds.@opennds[0].walledgarden_port_list)"
pidof opennds >/dev/null && echo opennds=UP || echo opennds=DOWN
ip -4 addr show br-guest | grep inet || true
curl -s -m 3 -o /dev/null -w 'cloud_health=%{http_code}\n' http://192.168.1.125:8080/health
curl -s -m 3 -o /dev/null -w 'cloud_portal=%{http_code}\n' http://192.168.1.125:8080/portal/
curl -s -m 3 -o /dev/null -w 'admin=%{http_code}\n' http://192.168.1.125:3000/
curl -s -m 3 -o /dev/null -w 'userdev=%{http_code}\n' http://192.168.1.125:3001/portal/
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
stdin, stdout, stderr = c.exec_command(SCRIPT, timeout=45)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
c.close()
