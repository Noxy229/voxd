# voxd

Offline dictation for Linux and Windows, with lightweight spelling correction.
Speech recognition weights are downloaded during installation. Dictation and
correction run locally afterwards.

## Install

### Windows 10/11 x64

Run **voxd-bootstrap-0.1.0-x64.exe**. The setup wizard installs Python 3.12 per user
if needed, an isolated application environment, Python/native-wheel dependencies,
Start menu shortcuts and the selected speech weights. It offers an optional
login startup entry. No system-wide Python PATH changes or administrator account
are required. Internet is needed during installation. Python installation uses
winget or an Authenticode-verified installer from python.org when winget is absent.

From a source checkout or extracted source archive, the same installation is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
# Force recognition weights below 1 GB:
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Compact
```

Installation lives under `%LOCALAPPDATA%\Programs\voxd`. Start **voxd** from the
Start menu; **Uninstall voxd** removes the application but retains models and
settings. With the EXE bootstrap, Windows Installed Apps also lists voxd.
A detailed bootstrap log is written to `%TEMP%\voxd-install.log`.
Microphone access must be enabled in Windows Privacy settings.

The separate fully bundled installer (`voxd-setup-…-x64.exe`) can be built on
Windows and needs no preinstalled Python. See [installer builds](docs/INSTALLERS.md).
The bootstrap EXE is compiled and available locally; actual installation on a
real Windows machine remains to be tested.

### Linux

Run the self-extracting **voxd-linux.run**, or from the source folder:

```bash
./install.sh
# Optional: keep speech weights below 1 GB, start at login:
./install.sh --compact --autostart
```

The installer installs system dependencies through apt, pacman, dnf or zypper
(using sudo for those packages), creates a private environment, downloads speech
weights and adds application/menu launchers. Run it as your desktop user.
`--no-system-deps` skips distribution package installation; Python 3.10+, venv,
PortAudio and the Qt/input libraries must then already exist. `--english` selects
an English correction dictionary; the default is German.

The application environment is under `$XDG_DATA_HOME/voxd/app` (normally
`~/.local/share/voxd/app`). Launch via the app menu or `~/.local/bin/voxd`.
Uninstall with `~/.local/share/voxd/app/uninstall.sh` (adjust for XDG_DATA_HOME).
Models and configuration survive uninstall. The installer does not install GPU
drivers or modify kernel input permissions.

## Correction without an LLM

The default editing pass uses [pyspellchecker](https://pyspellchecker.readthedocs.io/)
and a bundled frequency dictionary. The compressed German dictionary is about
**1.1 MB**, rather than the previous 1.1 GB Qwen weights. It is loaded once in the
background and reused. It fixes only unambiguous lowercase typos within one edit
step and ignores very rare proposed corrections. Names, ambiguous spellings,
URLs, email addresses, inline code, paths and identifiers are preserved.
Explicit commands such as “Fragezeichen” / “question mark” and “neue Zeile” /
“new line” are converted by rules.

This is conservative spelling cleanup, not a grammar engine. It cannot resolve
arbitrary spoken self-corrections such as “Tuesday, no, Wednesday”. The old LLM
mode remains available through `edit.mode = "llm"` and an explicit catalogue
model plus llama-server installation, but is never downloaded by the default
installer. Older version-1/2 settings migrate to dictionary editing. Existing LLM
weights are retained on disk so custom configurations are not deleted.

## Hardware and speech weights

The installer checks CPU threads, RAM, GPU vendor and reported VRAM before
choosing speech recognition precision:

- Normal or unknown-capacity machines: **Parakeet TDT 0.6B v3 INT8**, about 642 MB.
- At least 24 GB RAM, 8 threads and a reported GPU with at least 8 GB VRAM:
  **Parakeet full precision**, about 2.55 GB including `encoder.weights`.
- `--compact` / `-Compact` always forces INT8, including on powerful machines.

The extra large download is speech recognition, not spelling correction. Both
presets currently run on the CPU through the bundled sherpa-onnx runtime. GPU
recognition is not implied by GPU detection. Higher precision is not a guarantee
of better recognition; compare with your real speech before choosing it for
quality. The default INT8 recogniser already supports German and English.
Models are preloaded when voxd starts and stay resident until explicit release
or exit. Initial application startup still has a load time; repeated recording
activation does not reload weights. Runtime RAM exceeds model file size.

Model sources: [Parakeet INT8](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8),
[Parakeet full precision](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3).

## KDE Plasma

On Plasma Wayland the installer creates application launchers. Assign them in
**System Settings → Keyboard → Shortcuts → Add New → Application**:

| Action | Suggested shortcut | Command |
|---|---|---|
| Start/finish dictation | Meta+H | `voxctl toggle` |
| Dictate raw | Meta+Shift+H | `voxctl raw-toggle` |
| Discard | Meta+Alt+H | `voxctl cancel` |

Automatic Unicode paste requires `wl-clipboard` plus a running `ydotoold` with
uinput access. The packages are installed, but service and permission setup
varies by distribution. Without it, the transcript stays in the clipboard for
manual Ctrl+V. Plasma uses tray status, avoiding Qt overlay focus theft on KWin.
`xdotool` is reserved for X11. Klipper may retain transcripts in clipboard history.
Clipboard restoration preserves previous text, not arbitrary MIME data.

Windows registers shortcuts at each application startup. Existing shortcut
conflicts are reported; no exclusive shortcut availability is assumed.

## Settings and control

`voxd --setup` opens microphone/settings setup. `voxctl status`, `voxctl release`
and `voxctl quit` control the running instance. The frozen Windows application
also accepts `voxd.exe --ctl status`. `voxd-setup` or
`python -m voxd.bootstrap` prints the hardware plan without downloading;
`--apply` installs weights and saves settings after successful download.

Linux settings: `~/.config/voxd/config.toml`; models:
`~/.local/share/voxd/models` (XDG overrides respected).
Windows settings and models: `%APPDATA%\voxd\config` and `%APPDATA%\voxd\data`.
Normal logs and status do not include transcript text. Recordings are capped at
ten minutes; level monitoring retains no audio.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]' build
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/python -m build
.venv/bin/python tools/build_linux_installer.py
```

See [installer build/testing instructions](docs/INSTALLERS.md) and the earlier
[release verification notes](docs/RELEASE.md). No repository was made public.
The prior historical-author-email finding still applies before publication.

## License

MIT — see [LICENSE](LICENSE). Dependencies/model weights retain their licenses:
sherpa-onnx (Apache-2.0), Parakeet weights (CC-BY-4.0), pyspellchecker (MIT),
Qt/PySide6 (LGPL-3.0), optional Qwen3 (Apache-2.0), llama.cpp/whisper.cpp (MIT).
