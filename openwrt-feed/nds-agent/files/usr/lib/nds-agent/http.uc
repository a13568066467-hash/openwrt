'use strict';
/*
 * Minimal JSON-over-HTTPS client.
 *
 * curl is a hard dependency of nds-agent and is the primary transport;
 * uclient-fetch is kept as a fallback so the agent still reports on
 * stripped-down images where curl was dropped to save flash.
 *
 * Device credentials travel in the request body rather than in headers,
 * because uclient-fetch cannot set custom headers.
 */

import { popen, writefile, unlink } from 'fs';

const REQUEST_BODY_PATH = '/tmp/nds-agent-request.json';
const STATUS_SEPARATOR = '\n<<<STATUS:';

function shell_quote(value) {
	let escaped = replace(value ?? '', "'", "'\\''");

	return "'" + escaped + "'";
}

function run(command) {
	let proc = popen(command, 'r');

	if (!proc)
		return null;

	let out = proc.read('all');
	proc.close();

	return out;
}

function via_curl(url, timeout, insecure) {
	return run(`curl -sS ${insecure ? '-k' : ''} -m ${timeout} -X POST ` +
		`-H 'Content-Type: application/json' ` +
		`--data-binary @${REQUEST_BODY_PATH} ` +
		`-w '${STATUS_SEPARATOR}%{http_code}' ${shell_quote(url)} 2>/dev/null`);
}

function via_uclient(url, timeout, insecure) {
	return run(`uclient-fetch -q -O - ${insecure ? '--no-check-certificate' : ''} ` +
		`--timeout=${timeout} --post-file=${REQUEST_BODY_PATH} ` +
		`${shell_quote(url)} 2>/dev/null`);
}

/*
 * POST `payload` as JSON and return the decoded response, or null when the
 * request failed at any layer. Callers treat null as "cloud unreachable".
 */
function post_json(url, payload, options) {
	let timeout = options?.timeout ?? 15;
	let insecure = options?.insecure ?? false;

	try {
		writefile(REQUEST_BODY_PATH, sprintf('%J', payload));
	} catch (e) {
		warn(`nds-agent: cannot stage request body: ${e}\n`);

		return null;
	}

	let raw = via_curl(url, timeout, insecure);
	let body = raw;

	if (raw != null) {
		let marker = index(raw, STATUS_SEPARATOR);

		if (marker >= 0) {
			let status = int(substr(raw, marker + length(STATUS_SEPARATOR)));

			body = substr(raw, 0, marker);

			if (status < 200 || status >= 300) {
				warn(`nds-agent: ${url} returned HTTP ${status}\n`);
				unlink(REQUEST_BODY_PATH);

				return null;
			}
		}
	}

	if (body == null || length(trim(body)) == 0)
		body = via_uclient(url, timeout, insecure);

	unlink(REQUEST_BODY_PATH);

	if (body == null || length(trim(body)) == 0)
		return null;

	try {
		return json(body);
	} catch (e) {
		warn(`nds-agent: ${url} returned a non-JSON payload\n`);

		return null;
	}
}

export { post_json };
