"""Load only the terminal frontend from the wheel before application install."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheels = sorted(root.glob('voxd-*.whl'))
sys.path.insert(0, str(wheels[-1] if wheels else root / 'src'))
from voxd.installer_tui import main  # noqa: E402

raise SystemExit(main(['--payload', str(root), *sys.argv[1:]]))
