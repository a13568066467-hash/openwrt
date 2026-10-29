#!/usr/bin/env python3
"""Final audit: env.example integrity, committed binaries, doc/script consistency."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(r"d:\Users\Documents\project\openwrt")

print("=== cloud/.env.example raw lines ===")
raw = (ROOT / "cloud" / ".env.example").read_bytes()
print("bytes:", len(raw), "CR:", raw.count(b"\r"), "LF:", raw.count(b"\n"))
for i, line in enumerate(raw.split(b"\n"), 1):
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        text = line.decode("utf-8", "replace")
    print(f"{i:>3}| {text}")

print()
print("=== cloud/bin tracked in git? ===")
out = subprocess.run(
    ["git", "ls-files", "cloud/bin"], cwd=ROOT, capture_output=True, text=True
)
print(out.stdout.strip() or "(not tracked)")

print()
print("=== .gitignore bin rules ===")
gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
for i, line in enumerate(gi.splitlines(), 1):
    if "bin" in line or "dist" in line or "node_modules" in line:
        print(f"{i:>3}| {line}")

print()
print("=== docs/deployment.md: FAS level mention ===")
doc = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
for i, line in enumerate(doc.splitlines(), 1):
    if re.search(r"fas_secure|level\s*[0-9]|FAS", line, re.I):
        print(f"{i:>3}| {line}")

print()
print("=== docs/deployment.md: hardcoded IPs ===")
for i, line in enumerate(doc.splitlines(), 1):
    if re.search(r"192\.168\.\d+\.\d+", line):
        print(f"{i:>3}| {line}")
