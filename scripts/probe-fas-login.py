#!/usr/bin/env python3
import base64
import paramiko
import time

fas = base64.b64encode(
    b"clientip=192.168.100.10,clientmac=aa:bb:cc:dd:ee:ff,"
    b"gatewayname=NDS-Billing-Gateway,client_hid=hidtest,tok=tok1,"
    b"authdir=/opennds_auth/,gatewayaddress=192.168.100.1:2050,"
    b"originurl=http://status.client/"
).decode()
user = f"e2e{int(time.time()) % 100000}"
password = "testpass123"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    "192.168.1.1",
    username="root",
    password="1234567890",
    timeout=15,
    allow_agent=False,
    look_for_keys=False,
)

script = f"""
cat > /tmp/fas.b64 << 'EOF'
{fas}
EOF
FAS=$(cat /tmp/fas.b64)
curl -s -o /tmp/fas-out.html -w 'code=%{{http_code}}\\n' \
  -X POST "http://192.168.1.125:8080/fas?fas=$FAS" \
  -d "username={user}&password={password}&action=register&fas=$FAS"
echo USER={user}
echo '---'
head -c 800 /tmp/fas-out.html; echo
echo markers: portal=$(grep -c '/portal/' /tmp/fas-out.html || true) token=$(grep -c 'token=' /tmp/fas-out.html || true) statusclient=$(grep -c 'status.client' /tmp/fas-out.html || true) success=$(grep -c '认证成功' /tmp/fas-out.html || true)
pidof opennds >/dev/null && echo opennds=UP || echo opennds=DOWN
curl -s -o /dev/null -w portal_page=%{{http_code}}\\n http://192.168.1.125:8080/portal/
"""

stdin, stdout, stderr = client.exec_command(script, timeout=40)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("STDERR:", err)
client.close()
