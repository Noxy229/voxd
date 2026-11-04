#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$project_dir/.venv"
"$project_dir/.venv/bin/python" -m pip install -e "$project_dir"
printf '\nStart voxd: %q\n' "$project_dir/.venv/bin/voxd"
printf 'Editing requires llama-server on PATH. See README.md for desktop dependencies.\n'
