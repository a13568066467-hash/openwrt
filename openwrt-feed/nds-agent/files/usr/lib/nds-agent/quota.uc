'use strict';
/*
 * Combined (upload + download) quota enforcement.
 *
 * openNDS only supports separate upload and download quotas, so the combined
 * limit this product sells is enforced here instead.
 *
 * The cloud is the book of record for a user's balance, but the router has to
 * keep metering while it is offline. Each session therefore tracks a baseline:
 * the session byte count the cloud has already deducted from `remaining_bytes`.
 * Anything above the baseline has been spent but not yet reported.
 */

import { readfile, writefile, rename } from 'fs';
import { json_all, deauth } from './ndsctl.uc';

/* ndsctl reports per-session traffic counters in kilobytes. */
const COUNTER_UNIT_BYTES = 1024;

let quotas = {};
let sessions = {};

function normalise(mac) {
	return lc(trim(mac ?? ''));
}

function session_key(client) {
	return `${normalise(client.mac)}:${client.token ?? ''}:${client.session_start ?? 0}`;
}

function session_bytes(client) {
	let down = int(client.download_this_session ?? 0);
	let up = int(client.upload_this_session ?? 0);

	return (down + up) * COUNTER_UNIT_BYTES;
}

function load(path) {
	try {
		let raw = readfile(path);

		if (raw)
			quotas = json(raw) ?? {};
	} catch (e) {
		warn(`nds-agent: cannot read quota cache ${path}: ${e}\n`);
		quotas = {};
	}
}

function save(path) {
	let tmp = `${path}.tmp`;

	try {
		writefile(tmp, sprintf('%J', quotas));
		rename(tmp, path);
	} catch (e) {
		warn(`nds-agent: cannot persist quota cache ${path}: ${e}\n`);
	}
}

function get(mac) {
	return quotas[normalise(mac)];
}

/*
 * Record an authoritative balance from the cloud. `accounted_bytes` is the
 * session total the cloud has already booked, which becomes the new baseline.
 */
function set_remaining(mac, remaining_bytes, user_id, accounted_bytes) {
	let key = normalise(mac);

	quotas[key] = {
		user_id,
		remaining_bytes: int(remaining_bytes ?? 0),
		updated_at: time(),
	};

	if (accounted_bytes != null) {
		for (let sk in sessions) {
			if (sessions[sk].mac == key)
				sessions[sk].baseline = int(accounted_bytes);
		}
	}
}

function forget(mac) {
	delete quotas[normalise(mac)];
}

/*
 * Snapshot every authenticated client, pairing live counters with the portions
 * not yet reported to, and not yet booked by, the cloud.
 */
function snapshot() {
	let data = json_all();

	if (!data || !data.clients)
		return [];

	let live = [];
	let seen = {};

	for (let mac in data.clients) {
		let client = data.clients[mac];

		if (client.state != 'Authenticated')
			continue;

		let key = session_key(client);
		let total = session_bytes(client);

		seen[key] = true;
		sessions[key] ??= { mac: normalise(client.mac), baseline: 0, reported: 0 };

		push(live, {
			key,
			mac: normalise(client.mac),
			ip: client.ip,
			token: client.token,
			session_start: client.session_start,
			download_bytes: int(client.download_this_session ?? 0) * COUNTER_UNIT_BYTES,
			upload_bytes: int(client.upload_this_session ?? 0) * COUNTER_UNIT_BYTES,
			total_bytes: total,
			unreported_bytes: total - sessions[key].reported,
			uncredited_bytes: total - sessions[key].baseline,
		});
	}

	/* Drop bookkeeping for sessions openNDS no longer knows about. */
	for (let key in sessions) {
		if (!seen[key])
			delete sessions[key];
	}

	return live;
}

function mark_reported(key, total_bytes) {
	if (sessions[key])
		sessions[key].reported = int(total_bytes);
}

/*
 * Deauthenticate every client whose locally-tracked balance has run out.
 * Clients with no cached quota are left alone: the cloud authorised them, and
 * cutting them off on missing data would break the portal on a fresh boot.
 */
function enforce() {
	let expired = [];

	for (let client in snapshot()) {
		let quota = quotas[client.mac];

		if (!quota)
			continue;

		if (quota.remaining_bytes - client.uncredited_bytes > 0)
			continue;

		if (deauth(client.mac)) {
			push(expired, {
				mac: client.mac,
				total_bytes: client.total_bytes,
				remaining_bytes: quota.remaining_bytes,
			});
		}
	}

	return expired;
}

export { load, save, get, set_remaining, forget, snapshot, mark_reported, enforce };
