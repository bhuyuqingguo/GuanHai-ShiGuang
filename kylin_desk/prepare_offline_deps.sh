#!/usr/bin/env bash
# Run only on an Internet-connected preparation machine with the SAME OS/arch/Python.
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"
case "$(uname -m)" in x86_64) A=amd64;; aarch64) A=arm64;; *) echo "仅支持 AMD64/ARM64"; exit 2;; esac
python3 -m pip download --dest "offline_wheels/$A" --only-binary=:all: -r requirements-build.txt
printf '请将整个 kylin_desk 目录复制到同架构麒麟构建机，再运行 bash build_offline.sh\n'
