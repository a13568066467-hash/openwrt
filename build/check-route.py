#!/usr/bin/env python3
import socket, time, paramiko
HOST,LOCAL,PASS="192.168.1.1","192.168.1.125","1234567890"
def ssh(cmd,timeout=90):
  last=None
  for _ in range(8):
    try:
      sock=socket.create_connection((HOST,22),timeout=8,source_address=(LOCAL,0))
      c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      c.connect(HOST,username='root',password=PASS,sock=sock,timeout=15,banner_timeout=15,auth_timeout=15,allow_agent=False,look_for_keys=False)
      _,o,e=c.exec_command(cmd,timeout=timeout)
      out=o.read().decode()+e.read().decode(); c.close(); return out
    except Exception as ex:
      last=ex; time.sleep(1)
  raise RuntimeError(last)
print(ssh("echo OK; ip route; uci show firewall.guest_to_lan; uci show firewall.guest_masq_lan; ping -c1 -W2 8.8.8.8; echo DONE"))
