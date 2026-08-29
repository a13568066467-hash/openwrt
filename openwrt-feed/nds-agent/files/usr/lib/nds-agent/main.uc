#!/usr/bin/ucode
'use strict';
/*
 * nds-agent: combined-quota enforcement and cloud synchronisation for openNDS.
 *
 * Runs as a plain polling loop under procd rather than on uloop: the only
 * work is a periodic ndsctl sample, so an event loop would add a dependency
 * without buying anything.
 */

import { cursor } from 'uci';
import { mkdir, stat } from 'fs';
import { load, save, enforce } from './quota.uc';
import { report, heartbeat, load_seq } from './cloud.uc';

const VERSION = '1.0.0';
const STATE_DIR = '/etc/nds-agent';

function read_config() {
	let uci = cursor();

	uci.load('nds-agent');

	let get = (key, fallback) => uci.get('nds-agent', 'main', key) ?? fallback;

	return {
		version: VERSION,
		enabled: get('enabled', '1') != '0',
		cloud_url: rtrim(get('cloud_url', 'https://portal.local:8443'), '/'),
		poll_interval: int(get('poll_interval', 5)),
		report_interval: int(get('report_interval', 60)),
		request_timeout: int(get('request_timeout', 15)),
		insecure_tls: get('insecure_tls', '0') == '1',
		device_id: get('device_id', ''),
		device_secret: get('device_secret', ''),
		quota_file: get('quota_file', `${STATE_DIR}/quota.json`),
		backlog_file: get('backlog_file', `${STATE_DIR}/backlog.jsonl`),
		seq_file: get('seq_file', `${STATE_DIR}/seq`),
	};
}

function ensure_state_dir() {
	if (!stat(STATE_DIR))
		mkdir(STATE_DIR, 0o755);
}

let config = read_config();

if (!config.enabled) {
	warn('nds-agent: disabled by configuration, exiting\n');
	exit(0);
}

if (config.poll_interval < 1)
	config.poll_interval = 5;

ensure_state_dir();
load(config.quota_file);
load_seq(config.seq_file);

warn(`nds-agent ${VERSION} started (poll ${config.poll_interval}s, ` +
	`report ${config.report_interval}s, cloud ${config.cloud_url})\n`);

let registered = length(config.device_id) > 0;

if (!registered)
	warn('nds-agent: no device_id configured, running in local-only mode\n');

let elapsed = 0;

while (true) {
	try {
		for (let client in enforce())
			warn(`nds-agent: quota exhausted for ${client.mac}, deauthenticated\n`);

		elapsed += config.poll_interval;

		if (registered && elapsed >= config.report_interval) {
			elapsed = 0;
			report(config);
			heartbeat(config);
		}
	} catch (e) {
		/* A transient ndsctl or network failure must not kill the daemon. */
		warn(`nds-agent: cycle failed: ${e}\n`);
	}

	sleep(config.poll_interval * 1000);
}
