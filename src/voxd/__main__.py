"""Entry point: `voxd` starts the daemon and its interface."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if args and args[0] in ("-h", "--help"):
        print("voxd — local dictation\n\n"
              "  voxd            start the daemon (setup runs on first launch)\n"
              "  voxd --setup    force the setup window open\n"
              "  voxd --version  print the version\n\n"
              "  voxd --install-models --apply  hardware setup + downloads\n"
              "  voxd --ctl status              control (also works in Windows bundle)\n\n"
              "Control a running daemon with voxctl.")
        return 0

    if args and args[0] == "--version":
        from . import __version__
        print(__version__)
        return 0

    if args and args[0] == "--install-models":
        from .bootstrap import main as setup
        return setup(args[1:])
    if args and args[0] == "--ctl":
        from .cli import main as control
        return control(args[1:])

    from . import ipc
    if ipc.daemon_running():
        # A second launch should do something useful rather than fail: bring up
        # setup if asked, otherwise just say the daemon is already there.
        if args and args[0] == "--setup":
            print(ipc.send("setup"))
        else:
            print("voxd is already running (use voxctl to control it)")
        return 0

    from .app import Application
    app = Application(sys.argv[:1])
    if args and args[0] == "--setup":
        app.open_setup()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
