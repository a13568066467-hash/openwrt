#!/usr/bin/env python3
import socket, time, paramiko
HOST, LOCAL, PASS = "192.168.1.1", "192.168.1.125", "1234567890"
CMD = r"""
echo WAN:
ubus call network.interface.wan status 2>/dev/null | jsonfilter -e '@.up' -e '@["ipv4-address"][0].address' -e '@.errors[0].code' -e '@.proto'
uci -q get network.wan.proto; uci -q get network.wan.device; uci -q get network.wan.ifname
ip link show wan 2>&1 | head -2
ip -4 addr show wan 2>&1 | head -5
ip route show default 2>&1
echo CLIENTS:
ndsctl json 2>/dev/null | jsonfilter -e '@.client_list_length' 2>/dev/null
ndsctl clients 2>/dev/null | head -40
echo AUTH_SAMPLE:
ndsctl json 2>/dev/null | head -c 1500; echo
"""

def main():
  last=None
  for i in range(8):
    try:
      sock=socket.create_connection((HOST,22),timeout=8,source_address=(LOCAL,0))
      c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      c.connect(HOST,username='root',password=PASS,sock=sock,timeout=15,banner_timeout=15,auth_timeout=15,allow_agent=False,look_for_keys=False)
      _,o,e=c.exec_command(CMD,timeout=40)
      print(o.read().decode()+e.read().decode()); c.close(); return
    except Exception as ex:
      last=ex; print('retry',ex); time.sleep(2)
  raise SystemExit(last)
main()
