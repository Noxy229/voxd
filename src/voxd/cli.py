"""voxctl — the command line side of voxd."""

from __future__ import annotations

import json
import sys

from . import ipc

USAGE = """voxctl <command>

  toggle       start dictation, or finish and insert   (bound to Super+H)
  raw-toggle   same, but skip the editing pass
  cancel       discard the dictation in progress
  insert-raw   insert the unedited version of the last dictation
  status       what the daemon is doing right now
  release      drop the models from memory immediately
  reload       re-read the configuration file
  setup        open the setup window
  quit         stop the daemon
"""


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    cmd = args[0] if args else "toggle"

    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if cmd not in ipc.COMMANDS:
        print(f"unknown command: {cmd}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    try:
        reply = ipc.send(cmd)
    except ConnectionError:
        print("voxd is not running.\n"
              "  Linux:   systemctl --user start voxd\n"
              "  or just: voxd", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Status comes back as JSON; print it readably rather than as one blob.
    try:
        data = json.loads(reply)
        if isinstance(data, dict):
            width = max((len(k) for k in data), default=0)
            for k, v in data.items():
                print(f"  {k:<{width}}  {v}")
            return 0
    except (ValueError, TypeError):
        pass
    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
