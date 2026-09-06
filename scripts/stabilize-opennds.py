#!/usr/bin/env python3
import paramiko
import time

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

def run(cmd, timeout=90):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace") + stderr.read().decode(
        "utf-8", errors="replace"
    )

print("=== reset crash loop ===")
print(run(r"""
/etc/init.d/opennds stop 2>/dev/null || true
killall -9 opennds 2>/dev/null || true
ubus call service delete '{"name":"opennds","instance":"instance1"}' 2>/dev/null || true
rm -f /tmp/ndsctl.sock /var/run/opennds* 2>/dev/null || true
/etc/init.d/firewall restart
sleep 4
ifup guest
sleep 3
ip link set br-guest up
uci set opennds.@opennds[0].fwhook_enabled='0'
uci set opennds.@opennds[0].enabled='1'
uci commit opennds
/etc/init.d/opennds enable
/etc/init.d/opennds start
echo start_exit=$?
"""))

for i in range(8):
    time.sleep(5)
    st = run("pgrep -x opennds; echo status=$?; logread -e opennds | tail -4")
    print(f"--- +{(i+1)*5}s ---\n{st}")
    if st.strip().split("\n")[0].isdigit():
        print("=== SUCCESS ===")
        print(run("ndsctl status 2>/dev/null | head -20"))
        break
else:
    print("=== still down ===")
    print(run("ubus call service list | jsonfilter -e '@.opennds' 2>/dev/null; ls -la /etc/init.d/opennds; which opennds; opennds -h 2>&1 | head -3"))

print(run("curl -s -o /dev/null -w fas=%{http_code}\\n http://192.168.1.125:8080/fas; curl -s -o /dev/null -w portal=%{http_code}\\n http://192.168.1.125:8080/portal/"))
client.close()
