#!/usr/bin/env bash
# Run on the matching Kylin V10 target architecture. This script never uses network.
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"
PYTHON="${PYTHON:-python3}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ARCH_DIR=amd64 ;;
  aarch64) ARCH_DIR=arm64 ;;
  *) echo "错误：仅支持 AMD64/x86_64 或 ARM64/aarch64，当前为 $ARCH。" >&2; exit 2 ;;
esac
if [[ "$(uname -s)" != Linux ]]; then echo "错误：必须在银河麒麟 V10 / Linux 上构建。" >&2; exit 2; fi
WHEELS="offline_wheels/$ARCH_DIR"
[[ -d "$WHEELS" ]] || { echo "错误：缺少 $WHEELS，请先在有网准备机下载依赖（见 README）。" >&2; exit 2; }
TOOLS="tools/$ARCH_DIR"
if [[ ! -x "$TOOLS/xorriso" || ! -f "$TOOLS/xorriso-source.tar.gz" || ! -f "$TOOLS/xorriso-COPYING" ]]; then
  echo "错误：请先运行 prepare_xorriso.sh，准备本架构的 xorriso 及随附源码和许可证。" >&2
  exit 2
fi
[[ -d venv ]] || "$PYTHON" -m venv venv
# --no-index is intentional: an offline build must fail rather than access Internet.
venv/bin/python -m pip install --no-index --find-links "$WHEELS" -r requirements-build.txt
rm -rf build dist/GuanHaiShiGuang dist/GuanHaiShiGuang-kylin dist/tools
PYINSTALLER_ARGS=(
  --noconfirm --clean --onedir --windowed --contents-directory runtime
  --name GuanHaiShiGuang --specpath build --distpath dist --workpath build/work
  --add-data "$PWD/discore_512.png:." --add-data "$PWD/discore_64.png:." --add-data "$PWD/discore.png:."
  --add-binary "$PWD/$TOOLS/xorriso:$TOOLS"
  --add-data "$PWD/$TOOLS/xorriso-source.tar.gz:$TOOLS"
  --add-data "$PWD/$TOOLS/xorriso-COPYING:$TOOLS"
)
venv/bin/python -m PyInstaller "${PYINSTALLER_ARGS[@]}" main.py
printf '完成：%s\n' "$(readlink -f dist/GuanHaiShiGuang/GuanHaiShiGuang)"
file dist/GuanHaiShiGuang/GuanHaiShiGuang
