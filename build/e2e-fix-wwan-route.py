#!/usr/bin/env python3
import socket, paramiko, time
HOST,LOCAL,PASS="192.168.1.1","192.168.1.125","1234567890"
CMD=r"""
echo '## wwan'
ubus call network.interface.wwan status
echo
ip -4 addr show phy1-sta0 2>/dev/null
ip -4 route
# install default via wwan dhcp gateway
GW=$(ubus call network.interface.wwan status 2>/dev/null | jsonfilter -e '@.route[0].nexthop')
IP=$(ubus call network.interface.wwan status 2>/dev/null | jsonfilter -e '@["ipv4-address"][0].address')
echo GW=$GW IP=$IP
if [ -n "$GW" ]; then
  ip route replace default via "$GW" dev phy1-sta0 metric 5
fi
# backup via PC
ip route replace default via 192.168.1.125 dev br-lan metric 100
ip route
ping -c 2 -W 3 8.8.8.8 | tail -6
nslookup www.baidu.com 223.5.5.5 2>&1 | head -8
curl -v --connect-timeout 5 --max-time 8 -o /dev/null http://www.baidu.com/ 2>&1 | tail -20
# ensure opennds + guest
/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
/etc/init.d/opennds restart
sleep 3
ndsctl status 2>/dev/null | sed -n '1,25p'
"""
def ssh(cmd,timeout=120):
  for i in range(8):
    try:
      sock=socket.create_connection((HOST,22),timeout=8,source_address=(LOCAL,0))
      c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      c.connect(HOST,username='root',password=PASS,sock=sock,timeout=20,banner_timeout=20,auth_timeout=20,allow_agent=False,look_for_keys=False)
      _,o,e=c.exec_command(cmd,timeout=timeout); out=o.read().decode()+e.read().decode(); c.close(); return out
    except Exception as ex:
      print('retry',ex); time.sleep(2)
  raise SystemExit('fail')
print(ssh(CMD))
