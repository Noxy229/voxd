# Terminal installer

The current UI is `src/voxd/installer_tui.py`, using Textual. It launches the
existing platform installer as a subprocess only after explicit start. The
platform scripts report actual stages and model download fractions via
`VOXD_EVENT` JSON lines. Other output goes to a bounded, plain-text live log.
Installer options are structured argv, never interpolated shell commands.

## Build

```bash
.venv/bin/pip install -e '.[dev]' build
.venv/bin/python -m build
.venv/bin/python tools/build_linux_installer.py
# Cross-compile Windows console EXE and make the portable ZIP (MinGW-w64 required):
.venv/bin/python tools/build_terminal_installer.py
```

On Windows, install Python 3.12 x64 plus MinGW-w64 gcc/windres, then run
`powershell -NoProfile -ExecutionPolicy Bypass -File packaging/windows/build.ps1`.
The manually triggered Windows workflow does the same and uploads artifacts.
It does not publish a release or change repository visibility.

Current outputs:

- `dist/linux/voxd-linux.run`: executable self-extractor opening the TUI.
- `dist/windows/voxd-terminal-setup-x64.exe`: native x64 console launcher with an
  embedded wheel/PowerShell payload. It extracts to a unique temporary directory,
  prepares Python/Textual and opens the same terminal dashboard. No Inno UI.
- `dist/windows/voxd-terminal-installer.zip`: extract and run `Install.cmd`.

Before first dashboard startup, minimal Python/venv/Textual bootstrapping is
shown as normal terminal output; the app is not yet installed. Actual system
packages and application/model installation require the Start action. Neither
installer supplies GPU drivers or modifies repository visibility.

## Curl entry

`curl -fsSL https://raw.githubusercontent.com/Noxy229/voxd/main/install.sh | bash`
is implemented but **not yet publicly available**: the endpoint returned 404
when checked. Push to a readable repository before advertising this command as
live. The source archive and raw script use the same `main` branch. A locally
saved script without a sibling source tree/wheel also fetches the payload.
Interactive input is reopened from `/dev/tty`; noninteractive sessions require
`--non-interactive`. Tests stub the network download and exercise the real pipe
entry, archive extraction and forwarding of arguments without OS installation.

## Failure and cancellation

An exit code from the child backend controls success. Errors retain the log and
unlock choices for retry. A failed download does not mark model setup complete;
partial model files remain resumable. Q/Ctrl+C requests confirmation while
running. Cancellation reaps the user-owned backend process tree. During Linux
system-package installation the UI waits for the package manager to finish
before allowing cancellation; already installed packages are never rolled back.
There is no promise of an atomic rollback across OS packages, Python environment,
models and launchers. Windows uninstallation preserves model/settings directories.

## Verification boundaries

Headless Pilot tests exercise keyboard selection, actual subprocess progress and
failure/retry, live output while a cancellation dialog is open, cancellation and
small-terminal navigation. Existing application/model tests remain included.
The console launcher builds with `-Wall -Wextra -Werror` and its `--version` entry
is executed under Wine. PowerShell parsing, Bash syntax, package builds and the
Linux self-extractor's help path are checked. Screenshots are exported from the
actual Textual widgets with explicitly labelled example hardware/progress.

Real Windows Python/winget/DLL/microphone/SendInput behavior still needs a Windows
acceptance test. Root-owned package manager and sudo caching behavior must be
checked on target Linux distributions; no system-package installation is run
on the development desktop. The curl endpoint is not remotely end-to-end tested
because it is not published. The previous historical-author-email finding still
applies before publishing existing Git history.
