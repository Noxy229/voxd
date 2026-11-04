"""Build a single executable Linux bootstrap from an already built wheel."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = b'''#!/usr/bin/env bash
set -euo pipefail
payload_dir="$(mktemp -d)"
trap 'rm -rf -- "$payload_dir"' EXIT
payload_line="$(awk '/^__VOXD_PAYLOAD__$/{print NR+1;exit}' "$0")"
tail -n +"$payload_line" "$0" | tar -xz -C "$payload_dir"
bash "$payload_dir/install.sh" "$@"
exit 0
__VOXD_PAYLOAD__
'''


def main():
    wheel = ROOT / 'dist/voxd-0.1.0-py3-none-any.whl'
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for path in [wheel, ROOT / 'install.sh', ROOT / 'uninstall.sh',
                     ROOT / 'LICENSE', ROOT / 'README.md', ROOT / 'installer/launch_tui.py']:
            data = path.read_bytes()
            info = tarfile.TarInfo('installer/launch_tui.py' if path.name == 'launch_tui.py' else path.name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    out = ROOT / 'dist/linux/voxd-linux.run'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(HEADER + payload.getvalue())
    out.chmod(0o755)
    print(out)


if __name__ == '__main__':
    main()
