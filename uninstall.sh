#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -eq 0 ]]; then printf 'Run as your desktop user, without sudo.\n' >&2; exit 1; fi
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/voxd/app"
"$HOME/.local/bin/voxctl" quit 2>/dev/null || true
rm -f -- "$HOME/.local/bin/voxd" "$HOME/.local/bin/voxctl" \
    "${XDG_DATA_HOME:-$HOME/.local/share}/applications/org.voxd.App.desktop" \
    "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/org.voxd.App.desktop"
# Refuse an empty/unexpected target; downloaded models and settings are siblings.
[[ "$app_dir" == */voxd/app ]] || exit 1
rm -rf -- "$app_dir"
printf 'Application removed. Models and settings retained. Remove voxd shortcuts in desktop settings.\n'
