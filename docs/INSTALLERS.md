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

## Shared curl entry

The repository-root `install` file is a Bash/CMD polyglot. Both native entry
commands in README use this URL:
`https://raw.githubusercontent.com/Noxy229/voxd/main/install`.
Linux Bash downloads the latest `.run` plus `SHA256SUMS`, verifies the digest,
and runs the terminal UI. Git Bash/Cygwin detect Windows and dispatch to the
same file in native CMD. Native Windows CMD downloads
`installer/download_windows.ps1`, which validates architecture, retrieves the
latest console EXE and checksum, and refuses a checksum mismatch before execution.

The standard entry points use GitHub's `releases/latest/download` URLs. They
must therefore have a published, non-prerelease release with the documented
asset names. The source scripts remain usable for development. The older
`install.sh` pipe entry also supports fetching a full source payload and reopening
`/dev/tty`, but README's standard command now uses the release dispatcher.

Tests exercise Linux release selection, checksum rejection, unsupported OS
rejection, Git Bash dispatch, and source archive forwarding. Native CMD dispatch
is additionally tested under Wine with a no-op test executable; it does not
substitute for real Windows installation acceptance.

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
on the development desktop. Published bootstrap scripts and release checksums are verified anonymously
after release. Privacy audit and metadata cleanup are documented in RELEASE.md.
