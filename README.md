# voxd

Offline dictation for Linux and Windows, with lightweight spelling correction.
Speech recognition weights are downloaded during installation. Dictation and
correction run locally afterwards.

## Installation

The standard installation opens a keyboard-first terminal UI, detects your
operating system and hardware, and downloads the matching package from the
[latest release](https://github.com/Noxy229/voxd/releases/latest). No account is
needed. You can also download installers directly from
[Releases](https://github.com/Noxy229/voxd/releases).

### Standard command — Linux

```bash
curl -fsSL https://raw.githubusercontent.com/Noxy229/voxd/main/install | bash
```

### Standard command — Windows PowerShell

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/Noxy229/voxd/main/install -o "$env:TEMP\voxd-install.cmd"
if ($LASTEXITCODE -eq 0) { & "$env:TEMP\voxd-install.cmd" }
```

Both commands use **the same bootstrap URL**. It detects Linux versus Windows,
fetches the right release package and checks its SHA-256 checksum before running
it. Linux uses Bash; native Windows uses CMD/PowerShell. `curl` downloads the
bootstrap; the operating system's interpreter executes it. On Windows with Git
Bash, the Linux-style command also detects Windows and dispatches to its native
terminal installer. Windows packages currently support x64 only.

The dashboard shows CPU/RAM/GPU detection, model selection, dictionary language
and autostart choices alongside the current stage and live subprocess output.
Tab/Shift+Tab changes focus, arrows and Enter select options, Space toggles
checkboxes, S starts, R retries after failure, and Q requests cancellation.
Panels stack on narrow terminals; status and action buttons remain visible.

### Direct downloads / source installation

- **Linux:** download `voxd-linux.run` from Releases, then run `bash voxd-linux.run`.
- **Windows:** download `voxd-terminal-setup-x64.exe`, or extract
  `voxd-terminal-installer.zip` and run `Install.cmd`.
- **Source checkout:** run `./install.sh` on Linux, or `install.ps1` on Windows.

Internet is needed for the initial package and speech-weight downloads.
Minimal Python/venv/Textual bootstrapping happens before the dashboard opens;
the application, remaining system packages and speech weights install after
pressing S. On Linux, Python/venv itself may need a preliminary system-package
step if absent. Models remain usable offline afterwards.

The Linux dashboard can skip distribution packages when they already exist.
Supported package managers: apt, pacman, dnf and zypper. Sudo authentication takes
place on the real terminal; the password does not enter the log stream. System
package installation is allowed to finish before cancellation. ydotoold/uinput
permissions still depend on your distribution and are not granted automatically.

For automation, explicitly bypass the UI:

```bash
./install.sh --non-interactive --compact --no-system-deps
```

`--compact`, `--english` and `--autostart` also preselect interactive choices.
The Linux app environment is under `$XDG_DATA_HOME/voxd/app`, normally
`~/.local/share/voxd/app`. Start from the app menu or `~/.local/bin/voxd`.
Uninstall using `~/.local/share/voxd/app/uninstall.sh` (adjust for XDG_DATA_HOME).
Models/settings survive uninstall.

### Windows 10/11 x64

Run **voxd-terminal-setup-x64.exe** from Releases, or extract **voxd-terminal-installer.zip**
and double-click **Install.cmd**. Both open the terminal installer; there are no
Inno wizard pages in this path. Python 3.12 and the small Textual frontend are
prepared per-user first if needed. All application packages, model downloads,
Start-menu entries and optional autostart then run through the dashboard.
No system-wide Python PATH changes or administrator account are required.
Python is obtained through winget, with an Authenticode-verified python.org
installer as fallback. Internet is required during installation.

From source:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
# Automation without terminal interaction:
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NonInteractive -Compact
```

Application files live in `%LOCALAPPDATA%\Programs\voxd`. Start from the Start
menu; **Uninstall voxd** retains models/settings. Installer output is logged to
`%TEMP%\voxd-install.log`; the alternate-screen UI is excluded from transcripts.
Enable microphone access for desktop apps in Windows Privacy settings.
The console EXE is unsigned. It was cross-compiled and its version entry tested
under Wine; real Windows installation and input injection remain to be tested.
The older Inno definitions are legacy build sources, not the current UI.

See [installer builds and verification](docs/INSTALLERS.md).

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

See [installer build/testing instructions](docs/INSTALLERS.md) and the
[release verification notes](docs/RELEASE.md).

## License

MIT — see [LICENSE](LICENSE). Dependencies/model weights retain their licenses:
sherpa-onnx (Apache-2.0), Parakeet weights (CC-BY-4.0), pyspellchecker (MIT),
Qt/PySide6 (LGPL-3.0), optional Qwen3 (Apache-2.0), llama.cpp/whisper.cpp (MIT).
