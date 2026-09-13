"""Global shortcuts on Windows via RegisterHotKey.

Unlike Wayland, Windows lets an application claim a global hotkey directly, so
there is no config file to write and no compositor to ask. The daemon runs its
own message loop on a dedicated thread and posts the actions back.

NOT YET TESTED ON REAL HARDWARE.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading

from . import BindResult

user32 = ctypes.WinDLL("user32", use_last_error=True)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

_MODS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
         "shift": MOD_SHIFT, "super": MOD_WIN, "win": MOD_WIN,
         "windows": MOD_WIN, "meta": MOD_WIN}


def describe() -> str:
    return "Windows (registered directly with RegisterHotKey)"


def parse(accel: str) -> tuple[int, int]:
    """'Super+Shift+H' -> (modifier mask, virtual key code)."""
    mods, key = 0, None
    for part in (p.strip().lower() for p in accel.split("+")):
        if part in _MODS:
            mods |= _MODS[part]
        else:
            key = part
    if not key:
        raise ValueError(f"no key in accelerator: {accel}")
    if len(key) == 1:
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1                    # VK_F1 = 0x70
    else:
        named = {"space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
                 "escape": 0x1B, "esc": 0x1B}
        if key not in named:
            raise ValueError(f"unsupported key: {key}")
        vk = named[key]
    return mods | MOD_NOREPEAT, vk


class HotkeyThread(threading.Thread):
    """Owns the message loop. RegisterHotKey binds to the calling thread, so
    registration and the loop have to live together."""

    def __init__(self, bindings: dict[str, str], on_action):
        super().__init__(daemon=True)
        self.bindings = bindings
        self.on_action = on_action
        self.failed: dict[str, str] = {}
        self._ready = threading.Event()
        self._stop = False

    def run(self):
        ids = {}
        for i, (action, accel) in enumerate(self.bindings.items(), start=1):
            try:
                mods, vk = parse(accel)
            except ValueError as e:
                self.failed[action] = str(e)
                continue
            if user32.RegisterHotKey(None, i, mods, vk):
                ids[i] = action
            else:
                self.failed[action] = (
                    f"{accel} is already taken by another program")
        self._ready.set()

        msg = wt.MSG()
        while not self._stop and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                action = ids.get(msg.wParam)
                if action:
                    try:
                        self.on_action(action)
                    except Exception:
                        pass
        for i in ids:
            user32.UnregisterHotKey(None, i)

    def wait_ready(self, timeout=5):
        self._ready.wait(timeout)

    def stop(self):
        self._stop = True
        user32.PostThreadMessageW(threading.get_ident(), 0x0012, 0, 0)  # WM_QUIT


_thread: HotkeyThread | None = None


def apply(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    """`command` is unused here — Windows calls back in-process instead of
    spawning voxctl, which is faster and avoids a console window flashing."""
    global _thread
    from .. import ipc

    def dispatch(action):
        ipc.send({"toggle": "toggle", "raw": "raw-toggle",
                  "cancel": "cancel"}.get(action, "toggle"))

    if _thread is not None:
        _thread.stop()
    _thread = HotkeyThread(bindings, dispatch)
    _thread.start()
    _thread.wait_ready()
    if _thread.failed:
        detail = "; ".join(f"{k}: {v}" for k, v in _thread.failed.items())
        return BindResult(False, "some shortcuts could not be registered", detail)
    return BindResult(True, "registered with Windows")


def remove(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    global _thread
    if _thread is not None:
        _thread.stop()
        _thread = None
        return BindResult(True, "unregistered")
    return BindResult(False, "nothing registered")
