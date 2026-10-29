#!/usr/bin/env python3
import socket, paramiko
HOST,LOCAL,PASS="192.168.1.1","192.168.1.125","1234567890"
sock=socket.create_connection((HOST,22),timeout=8,source_address=(LOCAL,0))
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username="root",password=PASS,sock=sock,timeout=15,banner_timeout=15,auth_timeout=15,allow_agent=False,look_for_keys=False)
_,o,_=c.exec_command("uci show wireless; echo ---; iwinfo; echo ---; ls /sys/class/ieee80211; which wpa_supplicant; which wpad")
print(o.read().decode()); c.close()
