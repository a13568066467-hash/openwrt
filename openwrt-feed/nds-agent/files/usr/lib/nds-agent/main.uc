#!/usr/bin/ucode
'use strict';
/* NDS Billing Agent - main loop */

import { cursor } from 'uci';
import { timer } from 'uloop';
import { mkdir } from 'fs';
import { load_quota, check_and_enforce, save_quota } from '/usr/lib/nds-agent/quota.uc';
import { sync_report, sync_heartbeat } from '/usr/lib/nds-agent/sync.uc';

let uci = cursor();

function get_config() {
	uci.load('nds-agent');
	return {
		enabled: uci.get('nds-agent', 'main', 'enabled') != '0',
		cloud_url: uci.get('nds-agent', 'main', 'cloud_url') || 'https://portal.local:8443',
		poll_interval: int(uci.get('nds-agent', 'main', 'poll_interval') || 5),
		report_interval: int(uci.get('nds-agent', 'main', 'report_interval') || 60),
		device_id: uci.get('nds-agent', 'main', 'device_id') || '',
		device_secret: uci.get('nds-agent', 'main', 'device_secret') || '',
		quota_file: uci.get('nds-agent', 'main', 'quota_file') || '/etc/nds-agent/quota.json',
		events_file: uci.get('nds-agent', 'main', 'events_file') || '/tmp/nds-events.jsonl',
		pending_events: uci.get('nds-agent', 'main', 'pending_events') || '/etc/nds-agent/pending_events.jsonl',
	};
}

let config = get_config();

if (!config.enabled) {
	print('nds-agent disabled\n');
	exit(0);
}

mkdir('/etc/nds-agent');
load_quota(config.quota_file);

let report_tick = 0;

timer.create(config.poll_interval * 1000, () => {
	check_and_enforce(config.quota_file);

	report_tick += config.poll_interval;
	if (report_tick >= config.report_interval) {
		report_tick = 0;
		if (length(config.device_id) > 0) {
			sync_report(config);
			sync_heartbeat(config);
		}
	}

	return true;
});

uloop.run();
