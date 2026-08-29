'use strict';
/*
 * ndsctl communication.
 *
 * openNDS serialises ndsctl requests behind a lock and answers
 * "ndsctl thread is busy" when another client holds it, so every call
 * retries a few times before giving up.
 *
 * Exports are collected at the bottom: the ucode shipped with OpenWrt 25.12
 * requires a semicolon after every export statement, which rules out the
 * `export function f() {}` form.
 */

import { popen } from 'fs';

const NDSCTL = '/usr/bin/ndsctl';
const MAX_ATTEMPTS = 3;
const RETRY_DELAY_MS = 250;

function capture(args) {
	for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
		let proc = popen(`${NDSCTL} ${args} 2>/dev/null`, 'r');

		if (proc) {
			let out = proc.read('all');
			proc.close();

			if (out != null && index(out, 'busy') < 0)
				return out;
		}

		sleep(RETRY_DELAY_MS);
	}

	return null;
}

function json_all() {
	let out = capture('json');

	if (!out || length(trim(out)) == 0)
		return null;

	try {
		return json(out);
	} catch (e) {
		warn(`nds-agent: unparsable ndsctl json output: ${e}\n`);
		return null;
	}
}

function deauth(target) {
	return capture(`deauth ${target}`) != null;
}

function b64encode(data) {
	let out = capture(`b64encode "${replace(data ?? '', '"', '\\"')}"`);

	return out ? trim(out) : null;
}

function b64decode(data) {
	let out = capture(`b64decode "${replace(data ?? '', '"', '\\"')}"`);

	return out ? trim(out) : null;
}

export { json_all, deauth, b64encode, b64decode };
