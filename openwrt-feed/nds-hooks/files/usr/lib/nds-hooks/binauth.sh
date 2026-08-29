#!/bin/sh
# openNDS BinAuth hook for NDS billing.
#
# openNDS calls this as:
#   binauth.sh METHOD MAC BYTES_IN BYTES_OUT SESSION_START SESSION_END TOKEN CUSTOM
#
# For the "auth_client" method openNDS reads five values from stdout —
# session timeout, upload rate, download rate, upload quota, download quota —
# and treats a non-zero exit as a refusal. Every other method is a
# notification after the fact and expects no output.
#
# These quotas are openNDS's own separate up/down limits and act only as a
# backstop; the combined limit that is actually sold is enforced by nds-agent.
#
# Never call ndsctl commands that query the daemon here: openNDS blocks while
# this script runs, so a query would deadlock against its own lock.

EVENTS_FILE="/tmp/nds-events.jsonl"
EVENTS_MAX_LINES=2000

method="$1"
client_mac="$2"
bytes_in="$3"
bytes_out="$4"
session_start="$5"
session_end="$6"
client_token="$7"
customdata="$8"

sessiontimeout=0
upload_rate=0
download_rate=0
upload_quota=0
download_quota=0

# The FAS packs the authorised parameters into the custom field as base64 JSON.
# Decoded with busybox rather than `ndsctl b64decode` to keep this hook free of
# any round trip to the daemon.
if [ -n "$customdata" ]; then
	decoded=$(printf '%s' "$customdata" | base64 -d 2>/dev/null)

	if [ -n "$decoded" ]; then
		for field in sessiontimeout upload_rate download_rate upload_quota download_quota; do
			value=$(printf '%s' "$decoded" | jsonfilter -e "@.$field" 2>/dev/null)
			case "$value" in
				''|*[!0-9]*) ;;
				*) eval "$field=\$value" ;;
			esac
		done
	fi
fi

# A trace of session events, kept for debugging and bounded so a busy gateway
# cannot fill tmpfs. Nothing in the running system consumes this file.
printf '{"ts":"%s","method":"%s","mac":"%s","bytes_in":%s,"bytes_out":%s,"session_start":%s,"session_end":%s,"token":"%s"}\n' \
	"$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$method" "$client_mac" \
	"${bytes_in:-0}" "${bytes_out:-0}" "${session_start:-0}" "${session_end:-0}" \
	"${client_token:-none}" >> "$EVENTS_FILE" 2>/dev/null

if [ -f "$EVENTS_FILE" ]; then
	lines=$(wc -l < "$EVENTS_FILE" 2>/dev/null || echo 0)
	if [ "$lines" -gt "$EVENTS_MAX_LINES" ]; then
		tail -n $((EVENTS_MAX_LINES / 2)) "$EVENTS_FILE" > "$EVENTS_FILE.tmp" 2>/dev/null &&
			mv "$EVENTS_FILE.tmp" "$EVENTS_FILE"
	fi
fi

if [ "$method" = "auth_client" ]; then
	echo "$sessiontimeout $upload_rate $download_rate $upload_quota $download_quota"
fi

exit 0
