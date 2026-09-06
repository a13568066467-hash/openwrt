#!/bin/sh
# Restore guest bridge address + dnsmasq DHCP pool so WiFi clients get IPs.
#
# Symptom chain:
#   br-guest DOWN / DEVICE_CLAIM_FAILED
#   -> netifd has no guest IPv4
#   -> dnsmasq omits 192.168.100 dhcp-range
#   -> phones associate to NDS-WiFi but never get an IP
#
# Safe to run repeatedly (boot, hotplug, watchdog).

LOCK=/var/lock/nds-ensure-guest-dhcp.lock
LOG_TAG=nds-guest-dhcp

log() {
	logger -t "$LOG_TAG" "$@"
	echo "$@"
}

guest_has_ip() {
	ip -4 addr show br-guest 2>/dev/null | grep -q 'inet '
}

guest_dhcp_range_present() {
	grep -hq 'dhcp-range=.*,192\.168\.100\.' /var/etc/dnsmasq.conf* 2>/dev/null
}

has_wifi_radio() {
	ls /sys/class/ieee80211/*/ >/dev/null 2>&1
}

guest_has_eth1_port() {
	local ports
	ports=$(uci -q get network.guest_dev.ports 2>/dev/null) || return 1
	echo "$ports" | grep -qw eth1
}

ensure_dhcp_force() {
	# Without force, dnsmasq may skip guest while the iface briefly lacks an address.
	[ "$(uci -q get dhcp.guest.force)" = "1" ] && return 0
	uci -q set dhcp.guest.force='1'
	uci -q set dhcp.guest.ignore='0'
	uci -q set dhcp.guest.dhcpv4='server'
	uci -q commit dhcp
}

bring_members_up() {
	# Newifi / mt76 guest AP commonly named phy0-ap0; also try generic wlan APs.
	local iface
	for iface in phy0-ap0 phy1-ap0 wlan0-1 wlan1-1; do
		[ -d "/sys/class/net/$iface" ] || continue
		ip link set "$iface" up 2>/dev/null || true
	done
	ip link set br-guest up 2>/dev/null || true
}

force_guest_address() {
	local ipaddr netmask prefix
	ipaddr=$(uci -q get network.guest.ipaddr)
	netmask=$(uci -q get network.guest.netmask)
	[ -n "$ipaddr" ] || ipaddr='192.168.100.1'
	[ -n "$netmask" ] || netmask='255.255.255.0'
	prefix=24
	[ "$netmask" = "255.255.255.0" ] && prefix=24

	ip addr flush dev br-guest 2>/dev/null || true
	ip addr add "${ipaddr}/${prefix}" dev br-guest 2>/dev/null || true
	ip link set br-guest up 2>/dev/null || true
}

heal_guest_bridge() {
	# Headless QEMU: attach eth1 once.
	if ! has_wifi_radio && [ -d /sys/class/net/eth1 ] && ! guest_has_eth1_port; then
		uci add_list network.guest_dev.ports='eth1'
		uci commit network
		/etc/init.d/network reload
		sleep 3
	fi

	if ! ip link show br-guest >/dev/null 2>&1; then
		/etc/init.d/network reload
		sleep 3
	fi

	bring_members_up
	sleep 1

	# Prefer netifd ownership.
	ifdown guest 2>/dev/null || true
	sleep 1
	ifup guest 2>/dev/null || true
	sleep 2

	if ! guest_has_ip; then
		log "forcing guest address on br-guest"
		force_guest_address
		ifup guest 2>/dev/null || true
		sleep 1
	fi
}

restart_dhcp_stack() {
	/etc/init.d/dnsmasq restart >/dev/null 2>&1 || true
	sleep 2
	# openNDS binds gatewayinterface; restart only if enabled and bridge has an IP.
	if [ "$(uci -q get opennds.@opennds[0].enabled)" = "1" ] && guest_has_ip; then
		/etc/init.d/opennds restart >/dev/null 2>&1 || true
	fi
}

needs_heal() {
	guest_has_ip || return 0
	guest_dhcp_range_present || return 0
	pidof dnsmasq >/dev/null 2>&1 || return 0
	return 1
}

# Serialize concurrent hotplug/watchdog calls.
mkdir -p /var/lock
if command -v lock >/dev/null 2>&1; then
	lock -n "$LOCK" || exit 0
	trap 'lock -u "$LOCK"' EXIT
fi

ensure_dhcp_force

if ! needs_heal; then
	exit 0
fi

log "healing guest DHCP (br-guest / dnsmasq)"
heal_guest_bridge
restart_dhcp_stack

if guest_has_ip && guest_dhcp_range_present && pidof dnsmasq >/dev/null 2>&1; then
	log "guest DHCP OK: $(ip -4 addr show br-guest 2>/dev/null | awk '/inet /{print $2; exit}')"
	exit 0
fi

log "guest DHCP still unhealthy after heal"
exit 1
