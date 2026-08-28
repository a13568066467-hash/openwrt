#!/bin/bash
# OpenWrt build environment setup for WSL2 Ubuntu 22.04
set -euo pipefail

echo "==> Installing OpenWrt build dependencies..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential \
  clang \
  flex \
  bison \
  g++ \
  gawk \
  gcc-multilib \
  g++-multilib \
  gettext \
  git \
  libncurses5-dev \
  libncurses-dev \
  libssl-dev \
  python3 \
  python3-distutils \
  python3-setuptools \
  python3-dev \
  rsync \
  unzip \
  zlib1g-dev \
  file \
  wget \
  curl \
  ca-certificates \
  subversion \
  swig \
  time \
  xsltproc \
  zstd \
  libelf-dev \
  qemu-system-x86 \
  qemu-utils

OWRT_DIR="${HOME}/owrt/openwrt"
OWRT_TAG="v25.12.5"

echo "==> Cloning OpenWrt ${OWRT_TAG} to ${OWRT_DIR}..."
mkdir -p "${HOME}/owrt"
if [ ! -d "${OWRT_DIR}/.git" ]; then
  git clone --depth 1 --branch "${OWRT_TAG}" https://github.com/openwrt/openwrt.git "${OWRT_DIR}"
else
  echo "OpenWrt repo already exists, fetching ${OWRT_TAG}..."
  cd "${OWRT_DIR}"
  git fetch --depth 1 origin tag "${OWRT_TAG}" || git fetch origin
  git checkout "${OWRT_TAG}"
fi

cd "${OWRT_DIR}"
echo "==> Updating feeds..."
./scripts/feeds update -a
./scripts/feeds install -a

echo "==> OpenWrt build environment ready at ${OWRT_DIR}"
echo "    Checked out: $(git describe --tags --always)"
