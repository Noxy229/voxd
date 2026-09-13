"""Registering the global shortcut.

On Wayland an application cannot grab global keys — the protocol deliberately
forbids it, and anything that claims otherwise is reading /dev/input as root.
So voxd does not try. It asks the compositor to bind the key and run `voxctl`,
which is both the supported route and the one that keeps working when voxd is
restarted.

Each backend reports honestly whether it managed it, so the setup wizard can
fall back to telling the user what to bind by hand instead of pretending.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

IS_WINDOWS = sys.platform == "win32"


@dataclass
class BindResult:
    ok: bool
    how: str                 # what was done, or what the user must do
    manual_hint: str = ""    # non-empty when the user has to act


def backend():
    if IS_WINDOWS:
        from . import windows
        return windows
    from . import linux
    return linux


def describe() -> str:
    return backend().describe()


def apply(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    """`bindings` maps action name to accelerator, e.g. {"toggle": "Super+H"}."""
    return backend().apply(bindings, command)


def remove(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    return backend().remove(bindings, command)
