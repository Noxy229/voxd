# Installer builds and acceptance

## Available installation paths

- `install.ps1`: Windows per-user Python bootstrap, also embedded in the compiled
  `voxd-bootstrap-0.1.0-x64.exe` installer. Models are downloaded after detection.
- `install.sh`: Linux system dependencies, isolated application, models and
  launchers. `tools/build_linux_installer.py` wraps a built wheel and the shell
  scripts into a self-extracting `.run` without private source paths or Git data.
- `packaging/windows/voxd.iss`: fully bundled Windows application from PyInstaller.
  This build route runs on Windows and does not require Python on the target.

## Build on Windows

Python 3.12 x64 and Inno Setup 6 or 7 are build tools, not bundled-app target
prerequisites. Install Inno Setup and place ISCC.exe on PATH, then:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# To build only the small bootstrap EXE:
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -BootstrapOnly
```

Outputs are in `dist/windows`. The manually triggered `Windows installer` GitHub
Actions workflow builds both installer variants and uploads EXEs as artifacts;
it does not publish a release or change repository visibility.

The bootstrap can also be compiled using ISCC under Wine after building the
wheel: `ISCC packaging/windows/bootstrap.iss`. It was compiled this way locally
with the official Inno Setup 7.1.1 compiler (download SHA256 verified against the
publisher's GitHub release asset metadata). The PE is unsigned, so Windows may
show SmartScreen's unknown-publisher prompt. No signing identity is configured.

## What is checked locally

29 automated tests cover spelling with the actual German dictionary, protected
text, hardware profiles, compact override, transactional config writes, failed
model downloads and the existing application/Qt lifecycle tests. Ruff, Python
package builds and shell syntax checks pass. The PowerShell parser validates
all three installer/build scripts; this does not exercise Windows APIs.
Both Inno installer definitions compile (the bundled definition is syntax-tested
with a placeholder payload, not a runnable bundled Windows application).
The Linux self-extractor's `--help` path is run without installing packages.

One local dictionary run loaded in 0.17 s and corrected a synthetic German test
sentence in 0.8 ms after loading. These are single-run observations; dictionary
file size was 1,075,650 bytes compressed. No new LLM is required or downloaded.

## Windows test after switching machines

Run the bootstrap EXE, choose Compact if the total speech download should stay
below 1 GB, and inspect `%TEMP%\voxd-install.log` if setup fails. Verify Python
installation on a machine without Python, application launch from Start menu,
German microphone input, Meta+H registration/conflicts, insertion with umlauts
into Notepad and a browser, warm activation, optional login startup, a retry after
an interrupted download, and uninstall. Models/settings should remain after
uninstall. The bootstrap requires internet access and a usable Python package
index. If winget is missing, the official signed Python installer is verified
before execution.

Actual Windows installation, DLL loading, microphone and SendInput behavior are
not verified on this Linux machine. The optional PyInstaller bundle must still
be built and exercised on Windows. On Linux, package-manager commands and input
service permissions have not been applied to the current machine by these tests.
Full-precision recognition has not been downloaded or benchmarked locally;
INT8 remains the verified low-resource path. Neither preset uses GPU acceleration.
