'use strict';
/* ndsctl wrapper - uses fs.popen for compatibility */

import { popen, exec } from 'fs';

const NDSCTL = '/usr/bin/ndsctl';

export function ndsctl_json(mac) {
	let cmd = mac ? `${NDSCTL} json ${mac}` : `${NDSCTL} json`;
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

export function ndsctl_deauth(target) {
	exec(`${NDSCTL} deauth ${target} 2>/dev/null`);
}

export function ndsctl_auth(params) {
	exec(`${NDSCTL} auth ${params} 2>/dev/null`);
}

export function ndsctl_b64encode(data) {
	let p = popen(`${NDSCTL} b64encode "${replace(data, '"', '\\"')}"`, 'r');
	if (!p)
		return data;
	let out = trim(p.read('all'));
	p.close();
	return out || data;
}
