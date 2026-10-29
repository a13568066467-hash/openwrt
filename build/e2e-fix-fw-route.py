#!/usr/bin/env python3
import socket, time, paramiko
HOST,LOCAL,PASS="192.168.1.1","192.168.1.125","1234567890"
CMD=r"""
# firewall guest->lan + masq
uci -q delete firewall.guest_to_lan
uci set firewall.guest_to_lan=forwarding
uci set firewall.guest_to_lan.src='guest'
uci set firewall.guest_to_lan.dest='lan'
# lan masq
for s in $(uci show firewall | sed -n "s/^firewall\\.\\([^=]*\\)=zone$/\\1/p"); do
  [ "$(uci -q get firewall.$s.name)" = "lan" ] && uci set firewall.$s.masq='1' && uci set firewall.$s.mtu_fix='1'
done
uci commit firewall
fw4 reload 2>/dev/null || /etc/init.d/firewall restart
sleep 2
ip route replace default via 192.168.1.125 dev br-lan
echo '## nft masq'
nft list ruleset 2>/dev/null | grep -i masquerade | head -10
echo '## tests'
ping -c 1 -W 2 192.168.1.125; echo ping_pc=$?
ping -c 2 -W 3 8.8.8.8; echo ping8=$?
traceroute -n -w 2 -q 1 -m 5 8.8.8.8 2>&1 | head -10
curl -s -o /dev/null -w 'baidu=%{http_code}\n' --connect-timeout 5 --max-time 8 http://1.1.1.1/ || echo baidu=FAIL
"""
def ssh(cmd,timeout=90):
  for i in range(8):
    try:
      sock=socket.create_connection((HOST,22),timeout=8,source_address=(LOCAL,0))
      c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      c.connect(HOST,username='root',password=PASS,sock=sock,timeout=15,banner_timeout=15,auth_timeout=15,allow_agent=False,look_for_keys=False)
      _,o,e=c.exec_command(cmd,timeout=timeout); out=o.read().decode()+e.read().decode(); c.close(); return out
    except Exception as ex:
      print('retry',ex); time.sleep(1)
  raise SystemExit('ssh fail')
print(ssh(CMD))
