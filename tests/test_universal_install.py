import hashlib
import os
import subprocess
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / 'install'


def environment(tmp_path, *, valid_checksum=True, osname='Linux'):
    installer = tmp_path / 'voxd-linux.run'
    installer.write_text('#!/bin/bash\nprintf "LINUX_BACKEND:%s\\n" "$*"\n')
    checksum = hashlib.sha256(installer.read_bytes()).hexdigest() if valid_checksum else '0' * 64
    sums = tmp_path / 'sums'
    sums.write_text(f'{checksum}  voxd-linux.run\n')
    curl = tmp_path / 'curl'
    curl.write_text(f'''#!/bin/bash
url=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        https://*) url="$1" ;;
        -o) destination="$2"; shift ;;
    esac
    shift
done
case "$url" in
    */voxd-linux.run) cp '{installer}' "$destination" ;;
    */SHA256SUMS) cp '{sums}' "$destination" ;;
    *) exit 9 ;;
esac
''')
    curl.chmod(0o755)
    uname = tmp_path / 'uname'
    uname.write_text(f'#!/bin/bash\nprintf "%s\\n" "{osname}"\n')
    uname.chmod(0o755)
    return dict(os.environ, PATH=f'{tmp_path}:' + os.environ['PATH'])


def test_linux_dispatch_checks_release_and_preserves_arguments(tmp_path):
    result = subprocess.run(['bash', '-s', '--', '--compact'], input=ENTRY.read_text(),
                            text=True, capture_output=True, env=environment(tmp_path))
    assert result.returncode == 0, result.stderr
    assert 'LINUX_BACKEND:--compact' in result.stdout


def test_corrupt_release_is_never_executed(tmp_path):
    result = subprocess.run(['bash', '-s'], input=ENTRY.read_text(), text=True,
                            capture_output=True, env=environment(tmp_path, valid_checksum=False))
    assert result.returncode != 0
    assert 'LINUX_BACKEND:' not in result.stdout


def test_unsupported_os_is_rejected_before_downloading(tmp_path):
    result = subprocess.run(['bash', str(ENTRY)], text=True, capture_output=True,
                            env=environment(tmp_path, osname='Darwin'))
    assert result.returncode == 2
    assert 'Unsupported OS' in result.stderr


def test_git_bash_routes_to_native_windows_entry(tmp_path):
    env = environment(tmp_path, osname='MINGW64_NT-10.0')
    # No release download should run; only the shared entry is fetched.
    curl = tmp_path / 'curl'
    curl.write_text('#!/bin/bash\nwhile [[ $# -gt 0 ]]; do '
                    'if [[ "$1" == -o ]]; then printf "batch payload" > "$2"; exit; fi; shift; done\n')
    cygpath = tmp_path / 'cygpath'
    cygpath.write_text('#!/bin/bash\nprintf "%s\\n" "$2"\n')
    cmd = tmp_path / 'cmd.exe'
    cmd.write_text('#!/bin/bash\n[[ "$MSYS_NO_PATHCONV" == 1 && "$MSYS2_ARG_CONV_EXCL" == \'*\' ]] || exit 8\nprintf "WINDOWS_BACKEND\\n"\n')
    for file in (curl, cygpath, cmd):
        file.chmod(0o755)
    result = subprocess.run(['bash', str(ENTRY)], text=True, capture_output=True, env=env)
    assert result.returncode == 0, result.stderr
    assert 'WINDOWS_BACKEND' in result.stdout
    assert 'LINUX_BACKEND' not in result.stdout
