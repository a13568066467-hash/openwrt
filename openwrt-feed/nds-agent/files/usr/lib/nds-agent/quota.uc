'use strict';
/* Combined quota enforcement */

import { readfile, writefile, rename } from 'fs';
import { ndsctl_json, ndsctl_deauth } from '/usr/lib/nds-agent/ndsctl.uc';

let quota_cache = {};

export function load_quota(path) {
	try {
		let raw = readfile(path);
		if (raw)
			quota_cache = json(raw);
	} catch (e) {
		quota_cache = {};
	}
}

export function save_quota(path) {
	let tmp = path + '.tmp';
	writefile(tmp, stringify(quota_cache, true));
	rename(tmp, path);
}

export function set_user_quota(mac, remaining_bytes, user_id) {
	quota_cache[lc(mac)] = {
		user_id: user_id,
		remaining_bytes: remaining_bytes,
		updated_at: time(),
	};
}

export function get_user_quota(mac) {
	return quota_cache[lc(mac)] || null;
}

export function check_and_enforce(quota_path) {
	let data = ndsctl_json();
	if (!data || !data.clients)
		return [];

	let deauth_list = [];

	for (let mac in data.clients) {
		let c = data.clients[mac];
		if (c.state != 'Authenticated')
			continue;

		let dl = int(c.download_this_session || 0);
		let ul = int(c.upload_this_session || 0);
		let used_kb = dl + ul;
		let used_bytes = used_kb * 1024;

		let q = get_user_quota(c.mac);
		if (!q)
			continue;

		if (used_bytes >= q.remaining_bytes) {
			ndsctl_deauth(c.mac);
			deauth_list.push({
				mac: c.mac,
				used_bytes: used_bytes,
				remaining: q.remaining_bytes,
			});
		}
	}

	return deauth_list;
}

export function get_session_usage() {
	let data = ndsctl_json();
	if (!data || !data.clients)
		return [];

	let sessions = [];
	for (let mac in data.clients) {
		let c = data.clients[mac];
		if (c.state != 'Authenticated')
			continue;

		let dl = int(c.download_this_session || 0);
		let ul = int(c.upload_this_session || 0);

		sessions.push({
			mac: c.mac,
			ip: c.ip,
			token: c.token,
			session_start: c.session_start,
			download_kb: dl,
			upload_kb: ul,
			total_bytes: (dl + ul) * 1024,
		});
	}
	return sessions;
}
