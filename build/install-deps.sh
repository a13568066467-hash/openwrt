#!/bin/bash
# Install OpenWrt build dependencies (run as root in WSL)
set -eu

echo "=== Cleaning stale apt/sudo processes ==="
for p in $(ps -eo pid,cmd --no-headers | grep -E 'DEBIAN_FRONTEND|dpkg' | grep -v $$ | awk '{print $1}'); do
  kill -9 "$p" 2>/dev/null || true
done
sleep 1

rm -f /var/lib/apt/lists/lock /var/cache/apt/archives/lock /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend 2>/dev/null || true
dpkg --configure -a 2>/dev/null || true

echo "=== apt-get update ==="
DEBIAN_FRONTEND=noninteractive apt-get update -qq

echo "=== installing packages ==="
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential clang flex bison g++ gawk gettext git \
  libncurses-dev libssl-dev zlib1g-dev libelf-dev \
  python3 python3-dev python3-setuptools \
  rsync unzip zstd file wget curl ca-certificates \
  subversion swig time xsltproc cmake pkg-config libjson-c-dev \
  qemu-system-x86 qemu-utils

echo "=== verification ==="
for t in gcc g++ make python3 rsync unzip zstd file swig cmake; do
  printf '%-10s ' "$t"
  command -v "$t" >/dev/null 2>&1 && echo OK || echo MISSING
done
for h in /usr/include/ncurses.h /usr/include/openssl/ssl.h /usr/include/json-c/json.h; do
  printf '%-40s ' "$h"
  [ -f "$h" ] && echo OK || echo MISSING
done

echo "DEPS_INSTALL_DONE"
