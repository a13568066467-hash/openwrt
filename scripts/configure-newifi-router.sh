#!/bin/sh
# One-shot NDS billing setup for Newifi D2 lab (cloud on LAN PC).
set -e

CLOUD_IP="${NDS_CLOUD_IP:-192.168.1.125}"
DEVICE_ID="${NDS_DEVICE_ID:-NewWiFI}"
DEVICE_SECRET="${NDS_DEVICE_SECRET:-}"
# Must match cloud FAS_KEY — level-1 opennds_auth verifies tok=sha256(hid+faskey).
FAS_KEY="${NDS_FAS_KEY:?NDS_FAS_KEY must match cloud FAS_KEY}"

if [ -z "$DEVICE_SECRET" ]; then
	DEVICE_SECRET="$(dd if=/dev/urandom bs=16 count=1 2>/dev/null | hexdump -ve '1/1 "%02x"')"
fi

echo "=== NDS router configure cloud=$CLOUD_IP ==="

# --- Guest network ---
uci set network.guest_dev=device
uci set network.guest_dev.name='br-guest'
uci set network.guest_dev.type='bridge'
uci set network.guest_dev.macaddr='20:76:93:44:62:fe'

uci set network.guest=interface
uci set network.guest.device='br-guest'
uci set network.guest.proto='static'
uci set network.guest.ipaddr='192.168.100.1'
uci set network.guest.netmask='255.255.255.0'
uci set network.guest.delegate='0'
uci set network.guest.ipv6='0'

# --- Guest DHCP (force: dnsmasq must emit guest dhcp-range) ---
uci set dhcp.guest=dhcp
uci set dhcp.guest.interface='guest'
uci set dhcp.guest.start='100'
uci set dhcp.guest.limit='150'
uci set dhcp.guest.leasetime='12h'
uci set dhcp.guest.ignore='0'
uci set dhcp.guest.force='1'
uci set dhcp.guest.dhcpv4='server'
uci set dhcp.guest.ra='disabled'
uci set dhcp.guest.dhcpv6='disabled'
uci set dhcp.guest.ndp='disabled'
uci delete dhcp.guest.dhcp_option_force 2>/dev/null || true
uci add_list dhcp.guest.dhcp_option_force='114,http://home.me'
uci -q del_list dhcp.@dnsmasq[0].address='/home.me/192.168.100.1'
uci add_list dhcp.@dnsmasq[0].address='/home.me/192.168.100.1'

# The lab flow is IPv4 captive-portal only. Leaving wan6 half-configured causes
# repeated firewall4 reloads on this hardware and drops openNDS nft rules.
uci set network.wan6.disabled='1'

# --- Guest WiFi ---
uci set wireless.guest_radio0=wifi-iface
uci set wireless.guest_radio0.device='radio0'
uci set wireless.guest_radio0.mode='ap'
uci set wireless.guest_radio0.network='guest'
uci set wireless.guest_radio0.ssid='NDS-WiFi'
uci set wireless.guest_radio0.encryption='none'
uci set wireless.guest_radio0.isolate='1'

# --- Firewall guest zone ---
uci set firewall.guest=zone
uci set firewall.guest.name='guest'
uci set firewall.guest.network='guest'
uci set firewall.guest.input='REJECT'
uci set firewall.guest.output='ACCEPT'
uci set firewall.guest.forward='REJECT'

uci set firewall.guest_to_wan=forwarding
uci set firewall.guest_to_wan.src='guest'
uci set firewall.guest_to_wan.dest='wan'

uci set firewall.guest_dhcp=rule
uci set firewall.guest_dhcp.name='Allow-DHCP-Guest'
uci set firewall.guest_dhcp.src='guest'
uci set firewall.guest_dhcp.proto='udp'
uci set firewall.guest_dhcp.dest_port='67'
uci set firewall.guest_dhcp.family='ipv4'
uci set firewall.guest_dhcp.target='ACCEPT'

uci set firewall.guest_dns=rule
uci set firewall.guest_dns.name='Allow-DNS-Guest'
uci set firewall.guest_dns.src='guest'
uci set firewall.guest_dns.proto='tcp udp'
uci set firewall.guest_dns.dest_port='53'
uci set firewall.guest_dns.target='ACCEPT'

uci set firewall.guest_portal=rule
uci set firewall.guest_portal.name='Allow-openNDS-Guest'
uci set firewall.guest_portal.src='guest'
uci set firewall.guest_portal.proto='tcp'
uci set firewall.guest_portal.dest_port='2050'
uci set firewall.guest_portal.target='ACCEPT'

uci set firewall.allow_cloud_guest=rule
uci set firewall.allow_cloud_guest.name='Allow-Cloud-Guest'
uci set firewall.allow_cloud_guest.src='guest'
uci set firewall.allow_cloud_guest.dest='lan'
uci set firewall.allow_cloud_guest.dest_ip="$CLOUD_IP"
uci set firewall.allow_cloud_guest.proto='tcp'
# 8080/8443 = FAS+portal；3000/3001 = 管理端/用户端 Vite（实验室）
uci set firewall.allow_cloud_guest.dest_port='8080 8443 3000 3001'
uci set firewall.allow_cloud_guest.family='ipv4'
uci set firewall.allow_cloud_guest.target='ACCEPT'

uci -q delete firewall.block_guest_lan_private
uci set firewall.block_guest_lan_private=rule
uci set firewall.block_guest_lan_private.name='Block-Guest-LAN-Private'
uci set firewall.block_guest_lan_private.src='guest'
uci set firewall.block_guest_lan_private.dest='lan'
uci set firewall.block_guest_lan_private.dest_ip='192.168.1.0/24'
uci set firewall.block_guest_lan_private.family='ipv4'
uci set firewall.block_guest_lan_private.target='REJECT'

uci set firewall.guest_to_lan=forwarding
uci set firewall.guest_to_lan.src='guest'
uci set firewall.guest_to_lan.dest='lan'

# SNAT guest traffic when the upstream gateway is reachable via LAN (for PC-hosted lab/FAS).
uci -q delete firewall.guest_to_lan_nat
uci set firewall.guest_to_lan_nat='nat'
uci set firewall.guest_to_lan_nat.name='Guest-to-LAN-Masquerade'
uci set firewall.guest_to_lan_nat.src='lan'
uci set firewall.guest_to_lan_nat.src_ip='192.168.100.0/24'
uci set firewall.guest_to_lan_nat.target='MASQUERADE'
uci set firewall.guest_to_lan_nat.family='ipv4'

# --- openNDS FAS ---
# Lab uses level 1 (browser redirects to opennds_auth), matching the shipped
# nds-profile default. See docs/deployment.md.
[ -n "$(uci -q get opennds.@opennds[0])" ] || uci add opennds opennds

uci set opennds.@opennds[0].enabled='1'
uci set opennds.@opennds[0].gatewayinterface='br-guest'
uci set opennds.@opennds[0].gatewayname="$DEVICE_ID"
uci set opennds.@opennds[0].gatewayfqdn='home.me'
uci set opennds.@opennds[0].statuspath='/usr/lib/nds-hooks/client_status.sh'
uci set opennds.@opennds[0].fas_secure_enabled='1'
uci set opennds.@opennds[0].fasport='8080'
uci set opennds.@opennds[0].faspath='/fas'
uci delete opennds.@opennds[0].fasremotefqdn 2>/dev/null || true
uci set opennds.@opennds[0].fasremoteip="$CLOUD_IP"
uci set opennds.@opennds[0].faskey="$FAS_KEY"
uci delete opennds.@opennds[0].walledgarden_fqdn_list 2>/dev/null || true
uci add_list opennds.@opennds[0].walledgarden_fqdn_list="$CLOUD_IP"
uci delete opennds.@opennds[0].walledgarden_port_list 2>/dev/null || true
uci add_list opennds.@opennds[0].walledgarden_port_list='8080'
uci add_list opennds.@opennds[0].walledgarden_port_list='3000'
uci add_list opennds.@opennds[0].walledgarden_port_list='3001'
uci set opennds.@opennds[0].binauth='/usr/lib/nds-hooks/binauth.sh'
uci set opennds.@opennds[0].sessiontimeout='0'
uci set opennds.@opennds[0].checkinterval='5'
uci set opennds.@opennds[0].fwhook_enabled='1'

uci -q delete opennds.@opennds[0].users_to_router
uci add_list opennds.@opennds[0].users_to_router='allow tcp port 53'
uci add_list opennds.@opennds[0].users_to_router='allow udp port 53'
uci add_list opennds.@opennds[0].users_to_router='allow udp port 67'

# --- nds-agent ---
uci set nds-agent.main.enabled='1'
uci set nds-agent.main.cloud_url="http://${CLOUD_IP}:8080"
uci set nds-agent.main.device_id="$DEVICE_ID"
uci set nds-agent.main.device_secret="$DEVICE_SECRET"
uci set nds-agent.main.insecure_tls='1'
uci set nds-agent.main.report_interval='30'

uci commit network
uci commit dhcp
uci commit firewall
uci commit wireless
uci commit opennds
uci commit nds-agent

# Trust lab cloud TLS cert (for openNDS FAS probe via uclient-fetch)
if [ -f /tmp/nds-cloud.crt ]; then
	mkdir -p /etc/ssl/certs
	cp /tmp/nds-cloud.crt /etc/ssl/certs/nds-billing-ca.crt
	if [ -f /etc/ssl/cert.pem ]; then
		grep -q 'NDS-Billing-Lab' /etc/ssl/cert.pem 2>/dev/null || \
			cat /tmp/nds-cloud.crt >> /etc/ssl/cert.pem
	fi
fi

/etc/init.d/opennds stop 2>/dev/null || true
killall opennds 2>/dev/null || true
sleep 3

wifi reload
sleep 12
ifup guest
sleep 3
ip link set phy0-ap0 up 2>/dev/null || true
ip link set br-guest up 2>/dev/null || true

# Do not wifi-reload again after this — openNDS needs stable br-guest
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
	op="$(cat /sys/class/net/br-guest/operstate 2>/dev/null)"
	ip -4 addr show dev br-guest 2>/dev/null | grep -q 'inet 192.168.100.1' && [ "$op" = "up" ] && break
	sleep 3
	ifup guest 2>/dev/null
	ip link set br-guest up 2>/dev/null || true
done

/etc/init.d/dnsmasq restart
sleep 2
/etc/init.d/firewall reload
sleep 3

# Prefer shared self-heal (installed by apply-guest-dhcp-heal / nds-profile package).
if [ -x /usr/lib/nds-profile/ensure-guest-dhcp.sh ]; then
	/usr/lib/nds-profile/ensure-guest-dhcp.sh || true
fi

/etc/init.d/nds-late enable
# Start openNDS after firewall is quiet; avoid later firewall reloads
/etc/init.d/opennds enable
/etc/init.d/opennds restart
sleep 20
/etc/init.d/nds-agent restart

echo "=== verify ==="
echo "br-guest: $(cat /sys/class/net/br-guest/operstate 2>/dev/null)"
ip -4 addr show dev br-guest | grep inet || true
grep -E 'dhcp-range=set:guest' /var/etc/dnsmasq.conf.* 2>/dev/null || true
curl -s -o /dev/null -w "fas_http=%{http_code}\n" "http://${CLOUD_IP}:8080/fas" || echo "fas_http=fail"
curl -s -o /dev/null -w "portal_http=%{http_code}\n" "http://${CLOUD_IP}:8080/portal/" || echo "portal_http=fail"
pgrep -x opennds >/dev/null && echo "opennds=running" || pidof opennds >/dev/null && echo "opennds=running" || echo "opennds=DOWN"
logread -e opennds 2>/dev/null | tail -8 || true
ndsctl status 2>/dev/null | head -12 || true
