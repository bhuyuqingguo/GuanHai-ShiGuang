#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"

case "$(uname -m)" in
  x86_64) architecture=amd64 ;;
  aarch64) architecture=arm64 ;;
  *) echo "需要在 AMD64 或 ARM64 环境构建 xorriso。" >&2; exit 2 ;;
esac

destination="$PWD/tools/$architecture"
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT
cd -- "$build_dir"
archive=xorriso-1.5.6.tar.gz
curl --fail --silent --show-error --location --retry 3 -o "$archive" "https://ftp.gnu.org/gnu/xorriso/$archive"
printf '%s  %s\n' d4b6b66bd04c49c6b358ee66475d806d6f6d7486e801106a47d331df1f2f8feb "$archive" | sha256sum -c -
tar -xzf "$archive"
cd xorriso-1.5.6
./configure --disable-libreadline --disable-libedit
make -j"$(getconf _NPROCESSORS_ONLN)"
install -D -m 755 xorriso/xorriso "$destination/xorriso"
install -m 644 "../$archive" "$destination/xorriso-source.tar.gz"
install -m 644 COPYING "$destination/xorriso-COPYING"
