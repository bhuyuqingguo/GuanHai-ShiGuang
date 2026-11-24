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
[[ -d venv ]] || "$PYTHON" -m venv venv
# --no-index is intentional: an offline build must fail rather than access Internet.
venv/bin/python -m pip install --no-index --find-links "$WHEELS" -r requirements-build.txt
rm -rf build dist/GuanHaiShiGuang dist/GuanHaiShiGuang-kylin dist/tools
PYINSTALLER_ARGS=(
  --noconfirm --clean --onefile --windowed
  --name GuanHaiShiGuang --specpath build --distpath dist --workpath build/work
  --add-data "discore_512.png:." --add-data "discore_64.png:." --add-data "discore.png:."
)
if [[ -x "tools/$ARCH_DIR/xorriso" ]]; then
  # Embed into the one-file payload; the runtime finds it under sys._MEIPASS.
  PYINSTALLER_ARGS+=(--add-binary "tools/$ARCH_DIR/xorriso:tools/$ARCH_DIR")
  echo "将匹配 $ARCH_DIR 架构的 xorriso 嵌入单文件程序。"
else
  echo "警告：未提供 tools/$ARCH_DIR/xorriso，刻录功能仍需目标机离线安装 xorriso。" >&2
fi
venv/bin/python -m PyInstaller "${PYINSTALLER_ARGS[@]}" main.py
chmod +x dist/GuanHaiShiGuang
printf '完成：%s\n' "$(readlink -f dist/GuanHaiShiGuang)"
file dist/GuanHaiShiGuang
