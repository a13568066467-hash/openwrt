#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "192.168.1.1",
    username="root",
    password="1234567890",
    timeout=15,
    allow_agent=False,
    look_for_keys=False,
)
_, o, _ = c.exec_command(
    "opkg list-installed | grep -E 'opennds|nds-'; "
    "ls /etc/init.d/opennds /usr/bin/opennds /usr/lib/nds-hooks 2>&1; "
    "wifi status 2>/dev/null | head -c 400; echo"
)
print(o.read().decode())
c.close()
