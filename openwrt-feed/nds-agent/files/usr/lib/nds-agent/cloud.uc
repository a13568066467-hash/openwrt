'use strict';
/*
 * Cloud protocol: incremental usage reporting, backlog replay and command
 * execution.
 *
 * Reports are deltas keyed by (session_key, seq) so the cloud can discard
 * duplicates. `seq` is persisted because a router that reboots mid-session
 * must not restart numbering and have fresh reports mistaken for replays.
 */

import { readfile, writefile, unlink } from 'fs';
import { post_json } from './http.uc';
import { snapshot, mark_reported, set_remaining, load, save } from './quota.uc';
import { deauth } from './ndsctl.uc';

/* Bound the replay batch so a long outage cannot build an oversized request. */
const BACKLOG_BATCH = 50;

let seq = 0;
let online = true;

function is_online() {
	return online;
}

function load_seq(path) {
	try {
		seq = int(readfile(path) ?? 0);
	} catch (e) {
		seq = 0;
	}
}

function bump_seq(path) {
	seq++;

	try {
		writefile(path, `${seq}`);
	} catch (e) {
		warn(`nds-agent: cannot persist sequence counter: ${e}\n`);
	}

	return seq;
}

function read_backlog(path) {
	let entries = [];
	let raw;

	try {
		raw = readfile(path);
	} catch (e) {
		return entries;
	}

	if (!raw)
		return entries;

	for (let line in split(raw, '\n')) {
		if (length(trim(line)) == 0)
			continue;

		try {
			push(entries, json(line));
		} catch (e) {
			/* Skip a torn line rather than discarding the whole backlog. */
		}
	}

	return entries;
}

function write_backlog(path, entries) {
	if (length(entries) == 0) {
		unlink(path);

		return;
	}

	let lines = [];

	for (let entry in entries)
		push(lines, sprintf('%J', entry));

	try {
		writefile(path, join('\n', lines) + '\n');
	} catch (e) {
		warn(`nds-agent: cannot persist backlog ${path}: ${e}\n`);
	}
}

function append_backlog(path, entries) {
	let existing = read_backlog(path);

	for (let entry in entries)
		push(existing, entry);

	write_backlog(path, existing);
}

function apply_quota_updates(config, updates, accounted) {
	if (!updates || length(updates) == 0)
		return;

	load(config.quota_file);

	for (let update in updates)
		set_remaining(update.mac, update.remaining_bytes, update.user_id,
			accounted[lc(update.mac ?? '')]);

	save(config.quota_file);
}

function send(config, path, payload) {
	return post_json(`${config.cloud_url}${path}`, {
		device_id: config.device_id,
		device_secret: config.device_secret,
		...payload,
	}, { timeout: config.request_timeout, insecure: config.insecure_tls });
}

function replay_backlog(config) {
	let pending = read_backlog(config.backlog_file);

	if (length(pending) == 0)
		return true;

	while (length(pending) > 0) {
		let batch = slice(pending, 0, BACKLOG_BATCH);
		let response = send(config, '/api/v1/device/report', { reports: batch, replay: true });

		if (!response?.ok) {
			write_backlog(config.backlog_file, pending);

			return false;
		}

		pending = slice(pending, length(batch));
	}

	write_backlog(config.backlog_file, pending);

	return true;
}

function report(config) {
	let reports = [];
	let accounted = {};
	let session_keys = [];

	for (let client in snapshot()) {
		if (client.unreported_bytes <= 0)
			continue;

		push(session_keys, client.key);
		push(reports, {
			session_key: `${config.device_id}:${client.key}`,
			seq: bump_seq(config.seq_file),
			mac: client.mac,
			ip: client.ip,
			download_bytes: client.download_bytes,
			upload_bytes: client.upload_bytes,
			delta_bytes: client.unreported_bytes,
			total_bytes: client.total_bytes,
			timestamp: time(),
		});

		accounted[client.mac] = client.total_bytes;
	}

	if (length(reports) == 0) {
		if (online)
			replay_backlog(config);

		return null;
	}

	let response = send(config, '/api/v1/device/report', { reports });

	if (!response?.ok) {
		online = false;
		append_backlog(config.backlog_file, reports);

		return null;
	}

	online = true;

	for (let i = 0; i < length(reports); i++)
		mark_reported(session_keys[i], reports[i].total_bytes);

	apply_quota_updates(config, response.quota_updates, accounted);
	replay_backlog(config);

	return response;
}

function run_command(config, command) {
	switch (command?.action) {
	case 'deauth':
		deauth(command.mac);
		break;

	case 'set_quota':
		load(config.quota_file);
		set_remaining(command.mac, command.remaining_bytes, command.user_id, null);
		save(config.quota_file);
		break;

	default:
		warn(`nds-agent: ignoring unknown command '${command?.action}'\n`);
	}
}

function heartbeat(config) {
	let response = send(config, '/api/v1/device/heartbeat', {
		uptime: time(),
		online: true,
		agent_version: config.version,
	});

	if (!response?.ok) {
		online = false;

		return null;
	}

	online = true;

	for (let command in response.commands ?? [])
		run_command(config, command);

	return response;
}

export { report, heartbeat, load_seq, is_online };
