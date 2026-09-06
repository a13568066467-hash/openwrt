#!/usr/bin/env python3
"""Bring openNDS up without wifi reload flapping br-guest."""
import paramiko

HOST, USER, PASS = "192.168.1.1", "root", "1234567890"
SCRIPT = r"""
/etc/init.d/opennds stop 2>/dev/null || true
killall opennds 2>/dev/null || true
sleep 3

ifup guest 2>/dev/null || true
ip link set br-guest up 2>/dev/null || true
ip link set phy0-ap0 up 2>/dev/null || true

for i in $(seq 1 20); do
	op="$(cat /sys/class/net/br-guest/operstate 2>/dev/null)"
	if ip -4 addr show dev br-guest 2>/dev/null | grep -q '192.168.100.1' && [ "$op" = "up" ]; then
		break
	fi
	sleep 1
done
echo "operstate=$(cat /sys/class/net/br-guest/operstate 2>/dev/null)"
echo "fas_probe=$(curl -s -o /dev/null -w '%{http_code}' http://192.168.1.125:8080/fas)"
echo "portal_probe=$(curl -s -o /dev/null -w '%{http_code}' http://192.168.1.125:8080/portal/)"

uci set opennds.@opennds[0].enabled='1'
uci set opennds.@opennds[0].gatewayinterface='br-guest'
uci set opennds.@opennds[0].fasport='8080'
uci set opennds.@opennds[0].fas_secure_enabled='1'
uci set opennds.@opennds[0].fasremoteip='192.168.1.125'
uci delete opennds.@opennds[0].fasremotefqdn 2>/dev/null || true
uci delete opennds.@opennds[0].walledgarden_fqdn_list 2>/dev/null || true
uci add_list opennds.@opennds[0].walledgarden_fqdn_list='192.168.1.125'
uci delete opennds.@opennds[0].walledgarden_port_list 2>/dev/null || true
uci add_list opennds.@opennds[0].walledgarden_port_list='8080'
uci commit opennds

/etc/init.d/opennds enable
/etc/init.d/opennds start
sleep 18
if pgrep -x opennds >/dev/null; then
	echo STILL_RUNNING
else
	echo DEAD
fi
logread -e opennds | tail -25
ndsctl status 2>/dev/null | head -18 || true
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
stdin, stdout, stderr = client.exec_command(SCRIPT, timeout=180)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
client.close()
