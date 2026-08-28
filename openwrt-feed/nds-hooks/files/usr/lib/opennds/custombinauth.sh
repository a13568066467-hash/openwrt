#!/bin/sh
# NDS Billing custom BinAuth hook
# Called by openNDS on auth/deauth events.
# DO NOT call ndsctl directly from here (deadlock risk).

EVENTS_FILE="/tmp/nds-events.jsonl"
QUOTA_FILE="/etc/nds-agent/quota.json"

method="$1"
client_mac="$2"
bytes_in="$3"
bytes_out="$4"
session_start="$5"
session_end="$6"
client_token="$7"
customdata="$8"

# Defaults from custom field (base64 JSON set by FAS)
sessiontimeout=0
upload_rate=0
download_rate=0
upload_quota=0
download_quota=0

# Parse custom: base64 JSON {"user_id":N,"sessiontimeout":M,"upload_rate":U,...}
if [ -n "$customdata" ]; then
	decoded=$(echo "$customdata" | ndsctl b64decode 2>/dev/null || echo "")
	if [ -n "$decoded" ]; then
		sessiontimeout=$(echo "$decoded" | jsonfilter -e '@.sessiontimeout' 2>/dev/null || echo 0)
		upload_rate=$(echo "$decoded" | jsonfilter -e '@.upload_rate' 2>/dev/null || echo 0)
		download_rate=$(echo "$decoded" | jsonfilter -e '@.download_rate' 2>/dev/null || echo 0)
		upload_quota=$(echo "$decoded" | jsonfilter -e '@.upload_quota' 2>/dev/null || echo 0)
		download_quota=$(echo "$decoded" | jsonfilter -e '@.download_quota' 2>/dev/null || echo 0)
	fi
fi

# Log event for nds-agent consumption
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"ts":"%s","method":"%s","mac":"%s","bytes_in":%s,"bytes_out":%s,"session_start":%s,"session_end":%s,"token":"%s"}\n' \
	"$timestamp" "$method" "$client_mac" "${bytes_in:-0}" "${bytes_out:-0}" \
	"${session_start:-0}" "${session_end:-0}" "${client_token:-none}" >> "$EVENTS_FILE"

case "$method" in
	auth_client|client_auth|ndsctl_auth|preemptive_auth)
		# Allow access, echo quota params to openNDS
		echo "$sessiontimeout $upload_rate $download_rate $upload_quota $download_quota"
		exit 0
		;;
	*)
		exit 0
		;;
esac
