#!/usr/bin/env bash
# Per-user Linux installation; model/config directories survive uninstall.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
profile=auto
language=de
system_deps=1
autostart=0
for arg in "$@"; do
    case "$arg" in
        --compact) profile=compact ;;
        --english) language=en ;;
        --no-system-deps) system_deps=0 ;;
        --autostart) autostart=1 ;;
        --help) printf '%s\n' 'Usage: ./install.sh [--compact] [--english] [--no-system-deps] [--autostart]'; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
if [[ ${EUID} -eq 0 ]]; then
    printf 'Run as your desktop user, without sudo. Package installation requests sudo itself.\n' >&2
    exit 1
fi
if [[ $system_deps -eq 1 ]]; then
    command -v sudo >/dev/null || { printf 'sudo missing; install system dependencies and use --no-system-deps.\n' >&2; exit 1; }
    if command -v apt-get >/dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip libportaudio2 libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 wl-clipboard ydotool xdotool xclip
    elif command -v pacman >/dev/null; then
        sudo pacman -S --needed --noconfirm python python-pip portaudio libglvnd libxcb libxkbcommon-x11 wl-clipboard ydotool xdotool xclip
    elif command -v dnf >/dev/null; then
        sudo dnf install -y python3 python3-pip portaudio mesa-libEGL mesa-libGL libxkbcommon-x11 xcb-util-cursor wl-clipboard ydotool xdotool xclip
    elif command -v zypper >/dev/null; then
        sudo zypper --non-interactive install python3 python3-pip python3-virtualenv libportaudio2 libEGL1 libGL1 libxkbcommon-x11-0 libxcb-cursor0 wl-clipboard ydotool xdotool xclip
    else
        printf 'Unsupported package manager. Install Python 3.10+, venv, PortAudio, Qt runtime libraries and desktop input tools; retry --no-system-deps.\n' >&2
        exit 1
    fi
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/voxd/app"
venv_dir="$app_dir/venv"
bin_dir="$HOME/.local/bin"
mkdir -p "$app_dir" "$bin_dir"
if [[ -x "$venv_dir/bin/voxctl" ]]; then
    "$venv_dir/bin/voxctl" quit 2>/dev/null || true
fi
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
package="$project_dir"
for wheel in "$project_dir"/voxd-*.whl; do
    if [[ -f "$wheel" ]]; then package="$wheel"; break; fi
done
"$venv_dir/bin/python" -m pip install --upgrade --force-reinstall "$package"
"$venv_dir/bin/python" -m voxd.bootstrap --apply --profile "$profile" --language "$language"
for name in voxd voxctl; do
    printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$venv_dir/bin/$name" > "$bin_dir/$name"
    chmod +x "$bin_dir/$name"
done
cp -- "$project_dir/uninstall.sh" "$app_dir/uninstall.sh"
"$venv_dir/bin/python" - "$bin_dir/voxctl" <<'PYCODE'
import sys
from voxd import hotkeys
from voxd.config import Config
cfg=Config.load()
result=hotkeys.apply({key:cfg.get(f'hotkeys.{key}') for key in ('toggle','raw','cancel')},sys.argv[1])
print(result.how)
if result.manual_hint: print(result.manual_hint)
PYCODE
# Use Python for Desktop Entry escaping rather than interpolating shell paths.
"$venv_dir/bin/python" - "$venv_dir/bin/voxd" "$autostart" <<'PY'
import os,sys
from pathlib import Path
exe=sys.argv[1].replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
text=f'[Desktop Entry]\nType=Application\nName=voxd\nExec="{exe}"\nIcon=audio-input-microphone\nTerminal=false\nCategories=Utility;\n'
root=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'applications'
root.mkdir(parents=True,exist_ok=True)
(root/'org.voxd.App.desktop').write_text(text)
if sys.argv[2]=='1':
    root=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'autostart'
    root.mkdir(parents=True,exist_ok=True)
    (root/'org.voxd.App.desktop').write_text(text)
PY
printf '\nInstalled. Start with: %q\n' "$bin_dir/voxd"
printf 'Plasma Wayland: configure ydotoold/uinput for automatic paste; manual Ctrl+V works without it.\n'
printf 'Uninstall: %q\n' "$app_dir/uninstall.sh"
