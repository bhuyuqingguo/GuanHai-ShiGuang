#!/usr/bin/env bash
set -Eeuo pipefail
archive="$(realpath "$1")"
architecture="$2"
check_dir="$(mktemp -d)"
trap 'rm -rf -- "$check_dir"' EXIT
cd -- "$check_dir"
package="$check_dir/免安装 便携包"
mkdir -p "$package"
tar -xzf "$archive" -C "$package"
mapfile -t entries < <(find "$package" -mindepth 1 -maxdepth 1)
[[ ${#entries[@]} == 2 && -d "$package/runtime" && -x "$package/GuanHaiShiGuang" ]]
desktop_runtime="$package/runtime"
xorriso="$desktop_runtime/tools/$architecture/xorriso"
mkdir disc
printf 'portable\n' > disc/check.txt
LD_LIBRARY_PATH="$desktop_runtime" "$xorriso" -as mkisofs -quiet -o check.iso disc
LD_LIBRARY_PATH="$desktop_runtime" "$xorriso" -indev check.iso -ls / | grep -i "check[.]txt"

export HOME="$check_dir/home"
mkdir -p "$HOME/.config"
printf '%s\n' 'XDG_DESKTOP_DIR="$HOME/自定义桌面"' > "$HOME/.config/user-dirs.dirs"
xvfb-run -a bash -euo pipefail -s -- "$package" <<'SMOKE'
package="$1"
openbox >wm.log 2>&1 &
wm_pid=$!
app_pid=
trap '[[ -z "$app_pid" ]] || kill "$app_pid" 2>/dev/null || true; kill "$wm_pid" 2>/dev/null || true; cat smoke.log wm.log' EXIT
for attempt in {1..30}; do
  if wmctrl -m >/dev/null 2>&1; then break; fi
  sleep 0.2
done
wmctrl -m
"$package/GuanHaiShiGuang" >smoke.log 2>&1 &
app_pid=$!
shortcut="$HOME/自定义桌面/GuanHaiShiGuang.desktop"
for attempt in {1..30}; do
  kill -0 "$app_pid"
  window="$(wmctrl -lp | awk '/Kylin$/ {print $1; exit}')"
  if [[ -n "$window" && -x "$shortcut" ]]; then break; fi
  sleep 1
done
[[ -n "$window" && -x "$shortcut" ]]
desktop-file-validate "$shortcut"
grep -Fx "Exec=\"$package/GuanHaiShiGuang\"" "$shortcut"
wmctrl -ic "$window"
for attempt in {1..20}; do
  if xprop -id "$window" _NET_WM_STATE | grep -q _NET_WM_STATE_HIDDEN; then break; fi
  sleep 0.25
done
xprop -id "$window" _NET_WM_STATE | grep _NET_WM_STATE_HIDDEN
wmctrl -l | grep -F "$window"
wmctrl -ia "$window"
for attempt in {1..20}; do
  if ! xprop -id "$window" _NET_WM_STATE | grep -q _NET_WM_STATE_HIDDEN; then break; fi
  sleep 0.25
done
! xprop -id "$window" _NET_WM_STATE | grep -q _NET_WM_STATE_HIDDEN
test ! -s smoke.log
SMOKE
