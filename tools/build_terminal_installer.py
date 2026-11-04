"""Build the Windows console bootstrap without requiring a Windows host."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = ROOT / 'build/terminal-installer'
    out = ROOT / 'dist/windows'
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / 'voxd-terminal-installer.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for source, target in [
            ('dist/voxd-0.1.0-py3-none-any.whl', 'voxd-0.1.0-py3-none-any.whl'),
            ('install.ps1', 'install.ps1'), ('uninstall.ps1', 'uninstall.ps1'),
            ('installer/launch_tui.py', 'installer/launch_tui.py'),
            ('installer/Install.cmd', 'Install.cmd'), ('LICENSE', 'LICENSE'),
        ]:
            package.write(ROOT / source, target)
    windres = shutil.which('x86_64-w64-mingw32-windres') or shutil.which('windres')
    compiler = shutil.which('x86_64-w64-mingw32-gcc') or shutil.which('gcc')
    if not windres or not compiler:
        raise RuntimeError('MinGW-w64 gcc + windres required; ZIP installer is already built.')
    resource = work / 'payload.rc'
    resource.write_text(f'101 RCDATA "{archive.as_posix()}"\n'
                        f'102 RCDATA "{(ROOT / "packaging/windows/terminal_extract.ps1").as_posix()}"\n'
                        f'1 24 "{(ROOT / "packaging/windows/terminal_launcher.manifest").as_posix()}"\n')
    obj = work / 'payload.o'
    subprocess.run([windres, str(resource), '-o', str(obj)], check=True)
    exe = out / 'voxd-terminal-setup-x64.exe'
    subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-municode',
                    '-mconsole', '-Os', '-s', str(ROOT / 'packaging/windows/terminal_launcher.c'),
                    str(obj), '-o', str(exe)], check=True)
    print(exe)
    print(archive)


if __name__ == '__main__':
    main()
