'use strict';
/* Cloud sync - usage reporting and command pull */

import { readfile, writefile, popen } from 'fs';
import { get_session_usage, load_quota, set_user_quota, save_quota } from '/usr/lib/nds-agent/quota.uc';
import { ndsctl_deauth } from '/usr/lib/nds-agent/ndsctl.uc';

let last_reported = {};
let seq_counter = 0;
let cloud_online = true;

function http_post(url, body, headers) {
	let hdrs = '';
	for (let k in headers)
		hdrs += `-H "${k}: ${headers[k]}" `;

	let tmpfile = '/tmp/nds-agent-req.json';
	writefile(tmpfile, body);

	let cmd = `uclient-fetch -O - --post-file=${tmpfile} ${hdrs}"${url}" 2>/dev/null`;
	let p = popen(cmd, 'r');
	if (!p)
		return null;
	let out = p.read('all');
	p.close();
	if (!out || length(out) == 0)
		return null;
	try {
		return json(out);
	} catch (e) {
		return null;
	}
}

function append_pending(path, event) {
	let line = stringify(event) + '\n';
	try {
		let existing = readfile(path) || '';
		writefile(path, existing + line);
	} catch (e) {
		writefile(path, line);
	}
}

function flush_pending(pending_path, cloud_url, device_id, device_secret) {
	try {
		let raw = readfile(pending_path);
		if (!raw)
			return;

		let lines = split(raw, '\n');
		let url = `${cloud_url}/api/v1/device/report`;
		for (let line in lines) {
			if (length(trim(line)) == 0)
				continue;
			let resp = http_post(url, line, {
				'Content-Type': 'application/json',
				'X-Device-ID': device_id,
				'X-Device-Secret': device_secret,
			});
			if (resp && resp.ok)
				continue;
			return;
		}
		writefile(pending_path, '');
	} catch (e) {
	}
}

export function sync_report(config) {
	let sessions = get_session_usage();
	let reports = [];

	for (let s in sessions) {
		let sess = sessions[s];
		let key = `${config.device_id}:${sess.mac}:${sess.token}:${sess.session_start}`;
		let prev = last_reported[key] || 0;
		let delta = sess.total_bytes - prev;

		if (delta <= 0)
			continue;

		seq_counter++;
		let report = {
			session_key: key,
			seq: seq_counter,
			mac: sess.mac,
			ip: sess.ip,
			download_bytes: sess.download_kb * 1024,
			upload_bytes: sess.upload_kb * 1024,
			delta_bytes: delta,
			total_bytes: sess.total_bytes,
			timestamp: time(),
		};
		reports.push(report);
		last_reported[key] = sess.total_bytes;
	}

	if (length(reports) == 0)
		return;

	let url = `${config.cloud_url}/api/v1/device/report`;
	let body = stringify({ reports: reports });
	let resp = http_post(url, body, {
		'Content-Type': 'application/json',
		'X-Device-ID': config.device_id,
		'X-Device-Secret': config.device_secret,
	});

	if (resp && resp.ok) {
		cloud_online = true;
		if (resp.quota_updates) {
			load_quota(config.quota_file);
			for (let u in resp.quota_updates)
				set_user_quota(u.mac, u.remaining_bytes, u.user_id);
			save_quota(config.quota_file);
		}
		flush_pending(config.pending_events, config.cloud_url, config.device_id, config.device_secret);
	} else {
		cloud_online = false;
		for (let r in reports)
			append_pending(config.pending_events, r);
	}

	return resp;
}

export function sync_heartbeat(config) {
	let url = `${config.cloud_url}/api/v1/device/heartbeat`;
	let body = stringify({
		device_id: config.device_id,
		uptime: time(),
		online: true,
	});
	let resp = http_post(url, body, {
		'Content-Type': 'application/json',
		'X-Device-ID': config.device_id,
		'X-Device-Secret': config.device_secret,
	});

	if (resp && resp.commands) {
		for (let cmd in resp.commands) {
			switch (cmd.action) {
			case 'deauth':
				ndsctl_deauth(cmd.mac);
				break;
			case 'set_quota':
				load_quota(config.quota_file);
				set_user_quota(cmd.mac, cmd.remaining_bytes, cmd.user_id);
				save_quota(config.quota_file);
				break;
			}
		}
	}

	return resp;
}

export function is_cloud_online() {
	return cloud_online;
}
