#!/usr/bin/env python3
"""Register one flashed router in the cloud from its nds-agent UCI identity."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import paramiko


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router-host", default=os.environ.get("NDS_ROUTER_HOST", "192.168.1.1"))
    parser.add_argument("--router-user", default=os.environ.get("NDS_ROUTER_USER", "root"))
    parser.add_argument(
        "--router-pass",
        default=os.environ.get("NDS_ROUTER_PASS") or os.environ.get("NDS_ROUTER_PASSWORD", "1234567890"),
    )
    parser.add_argument("--cloud-base", default=os.environ.get("NDS_CLOUD_BASE", "http://192.168.1.125:8080"))
    parser.add_argument(
        "--token",
        default=os.environ.get("NDS_DEVICE_REGISTER_TOKEN") or os.environ.get("DEVICE_REGISTER_TOKEN", ""),
        help="Provisioning token configured on the cloud.",
    )
    parser.add_argument("--name", default=os.environ.get("NDS_ROUTER_NAME", ""))
    return parser.parse_args()


def ssh_read_identity(args: argparse.Namespace) -> tuple[str, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.router_host,
        username=args.router_user,
        password=args.router_pass,
        timeout=12,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        command = """
set -e
id="$(uci -q get nds-agent.main.device_id)"
secret="$(uci -q get nds-agent.main.device_secret)"
printf '%s\\n%s\\n' "$id" "$secret"
"""
        _, stdout, stderr = client.exec_command(command, timeout=20)
        out = stdout.read().decode("utf-8", errors="replace").splitlines()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError(err or f"router command exited {code}")
    finally:
        client.close()

    device_id = out[0].strip() if len(out) > 0 else ""
    device_secret = out[1].strip() if len(out) > 1 else ""
    if not device_id or len(device_secret) < 16:
        raise RuntimeError("router nds-agent identity is incomplete")
    return device_id, device_secret


def post_register(args: argparse.Namespace, device_id: str, device_secret: str) -> int:
    if not args.token:
        raise RuntimeError("DEVICE_REGISTER_TOKEN or NDS_DEVICE_REGISTER_TOKEN is required")

    body = json.dumps(
        {
            "device_id": device_id,
            "name": args.name or device_id,
            "secret": device_secret,
        }
    ).encode()
    req = urllib.request.Request(
        args.cloud_base.rstrip("/") + "/api/v1/device/register",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Device-Register-Token", args.token)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=10) as resp:
            print(f"registered device_id={device_id} status={resp.status}")
            return 0
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace").strip()
        print(f"register failed status={exc.code} body={body_text}", file=sys.stderr)
        return 1


def main() -> int:
    args = parse_args()
    device_id, device_secret = ssh_read_identity(args)
    print(f"router identity device_id={device_id} secret_present=1")
    return post_register(args, device_id, device_secret)


if __name__ == "__main__":
    raise SystemExit(main())
