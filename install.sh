#!/usr/bin/env bash
# Per-user Linux installation; model/config directories survive uninstall.
set -euo pipefail
# curl | bash has no source directory. Fetch the complete source payload first.
script_path="${BASH_SOURCE[0]:-}"
local_payload=0
if [[ -n "$script_path" && -f "$script_path" && "$script_path" != /dev/* ]]; then
    candidate_dir="$(cd -- "$(dirname -- "$script_path")" && pwd)"
    if [[ -f "$candidate_dir/pyproject.toml" && -f "$candidate_dir/src/voxd/bootstrap.py" ]] || compgen -G "$candidate_dir/voxd-*.whl" >/dev/null; then
        local_payload=1
    fi
fi
if [[ $local_payload -eq 0 ]]; then
    payload_dir="$(mktemp -d)"
    trap 'rm -rf -- "$payload_dir"' EXIT
    archive_url="https://github.com/Noxy229/voxd/archive/refs/heads/main.tar.gz"
    printf 'voxd: lade Installationsdateien …\n'
    curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$archive_url" -o "$payload_dir/source.tar.gz"
    tar -xzf "$payload_dir/source.tar.gz" --strip-components=1 -C "$payload_dir"
    if ( : </dev/tty ) 2>/dev/null; then
        bash "$payload_dir/install.sh" "$@" </dev/tty
    else
        bash "$payload_dir/install.sh" "$@"
    fi
    exit $?
fi
project_dir="$(cd -- "$(dirname -- "$script_path")" && pwd)"
profile=auto
language=de
system_deps=1
autostart=0
non_interactive=0
for arg in "$@"; do
    case "$arg" in
        --non-interactive) non_interactive=1 ;;
        --compact) profile=compact ;;
        --english) language=en ;;
        --no-system-deps) system_deps=0 ;;
        --autostart) autostart=1 ;;
        --help) printf '%s\n' 'Usage: ./install.sh [--compact] [--english] [--no-system-deps] [--autostart] [--non-interactive]'; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
if [[ ${EUID} -eq 0 ]]; then
    printf 'Run as your desktop user, without sudo. Package installation requests sudo itself.\n' >&2
    exit 1
fi
if [[ $non_interactive -eq 0 ]]; then
    if [[ ! -t 0 || ! -t 1 ]]; then
        if ( : </dev/tty >/dev/tty ) 2>/dev/null; then
            exec </dev/tty >/dev/tty
        else
            printf 'Ein Terminal wird benötigt. Für unbeaufsichtigte Installation: --non-interactive.\n' >&2
            exit 2
        fi
    fi
    printf 'voxd: bereite Terminal-UI vor (Python + Textual) …\n'
    if ! command -v python3 >/dev/null; then
        if [[ $system_deps -eq 0 ]]; then
            printf 'Python fehlt; --no-system-deps erlaubt keine Paketinstallation.\n' >&2
            exit 1
        fi
        if command -v apt-get >/dev/null; then sudo apt-get update; sudo apt-get install -y python3 python3-venv
        elif command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm python
        elif command -v dnf >/dev/null; then sudo dnf install -y python3
        elif command -v zypper >/dev/null; then sudo zypper --non-interactive install python3 python3-virtualenv
        else printf 'Python 3.10+ fehlt. Bitte installieren und erneut starten.\n' >&2; exit 1
        fi
    fi
    python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
    bootstrap_dir="${XDG_CACHE_HOME:-$HOME/.cache}/voxd/installer-venv"
    if ! python3 -m venv "$bootstrap_dir"; then
        if [[ $system_deps -eq 1 ]] && command -v apt-get >/dev/null; then
            sudo apt-get install -y python3-venv
            python3 -m venv "$bootstrap_dir"
        else exit 1; fi
    fi
    "$bootstrap_dir/bin/python" -m pip install --disable-pip-version-check 'textual>=8.2,<9' 'tomli>=2'
    tui_args=(--profile "$profile" --language "$language")
    [[ $autostart -eq 0 ]] || tui_args+=(--autostart)
    [[ $system_deps -eq 1 ]] || tui_args+=(--no-system-deps)
    "$bootstrap_dir/bin/python" "$project_dir/installer/launch_tui.py" "${tui_args[@]}"
    exit $?
fi
stage() { printf 'VOXD_EVENT {"stage":"%s"}\n' "$1"; }
stage preflight
# The TUI already authenticated sudo. Never request a password through its log pipe.
if [[ "${VOXD_INSTALL_EVENTS:-}" == 1 && $system_deps -eq 1 ]]; then
    sudo -n -v || { printf 'sudo-Anmeldung abgelaufen; Installation erneut starten.\n' >&2; exit 1; }
    sudo() { command sudo -n "$@"; }
fi
stage dependencies
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
stage environment
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
package="$project_dir"
for wheel in "$project_dir"/voxd-*.whl; do
    if [[ -f "$wheel" ]]; then package="$wheel"; break; fi
done
stage application
"$venv_dir/bin/python" -m pip install --upgrade --force-reinstall "$package"
stage models
"$venv_dir/bin/python" -m voxd.bootstrap --apply --profile "$profile" --language "$language"
stage shortcuts
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
