#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.1.1", username="root", password="1234567890", timeout=8, allow_agent=False, look_for_keys=False)
cmd = r"""
echo FAS=$(uci -q get opennds.@opennds[0].fasremoteip):$(uci -q get opennds.@opennds[0].fasport)
echo WG=$(uci -q get opennds.@opennds[0].walledgarden_fqdn_list)
echo WGP=$(uci -q get opennds.@opennds[0].walledgarden_port_list)
uci show firewall | grep -A8 allow_cloud || true
# from router to cloud
uclient-fetch -q -O - -T 3 http://192.168.1.125:8080/health; echo
uclient-fetch -q -O - -T 3 http://192.168.1.125:8080/fas; echo
# guest zone forward rules
nft list ruleset 2>/dev/null | grep -iE '192.168.1.125|8080|guest' | head -40
"""
_, o, e = c.exec_command(cmd, timeout=40)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
