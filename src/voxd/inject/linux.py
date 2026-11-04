"""Typing into other windows on Linux.

Three rungs, in this order:

  wtype      Wayland's virtual-keyboard protocol. Handles Unicode correctly —
             accents, umlauts, em dashes — independently of keyboard layout.
  ydotool    Goes through the kernel's uinput device, so it reaches XWayland
             windows and anything that ignores the virtual-keyboard route.
             ASCII only, which is why it sits below wtype.
  clipboard  Copy and press paste. Works everywhere, including Electron apps.
             Restores the previous clipboard contents afterwards.

On X11 the first rung is xdotool instead.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

WAYLAND = os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(
    os.environ.get("WAYLAND_DISPLAY"))


def _run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=kw.pop("timeout", 30), **kw)


# ------------------------------------------------------------- focused window

def focused_app() -> str:
    """Window class of the focused window, used as the cache key."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        try:
            out = _run(["hyprctl", "activewindow", "-j"], timeout=2).stdout
            return json.loads(out).get("class") or "unknown"
        except Exception:
            pass
    if os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
        try:
            tree = json.loads(_run(["swaymsg", "-t", "get_tree"], timeout=2).stdout)

            def focused(node):
                if node.get("focused"):
                    return node
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    hit = focused(child)
                    if hit:
                        return hit
                return None
            node = focused(tree) or {}
            return node.get("app_id") or (node.get("window_properties") or {}).get(
                "class") or "unknown"
        except Exception:
            pass
    if not WAYLAND and shutil.which("xdotool"):
        try:
            wid = _run(["xdotool", "getactivewindow"], timeout=2).stdout.strip()
            cls = _run(["xdotool", "getwindowclassname", wid], timeout=2).stdout
            return cls.decode().strip() or "unknown"
        except Exception:
            pass
    return "unknown"


# ------------------------------------------------------------------- rungs

def type_wtype(text: str) -> bool:
    if not shutil.which("wtype"):
        return False
    return _run(["wtype", "--", text]).returncode == 0


def type_xdotool(text: str) -> bool:
    if not shutil.which("xdotool"):
        return False
    return _run(["xdotool", "type", "--clearmodifiers", "--delay", "2", "--", text]
                ).returncode == 0


def type_ydotool(text: str) -> bool:
    if not shutil.which("ydotool"):
        return False
    if not text.isascii():
        return False                      # ydotool cannot produce non-ASCII
    if _run(["pgrep", "-x", "ydotoold"]).returncode != 0:
        return False                      # the daemon is not running
    return _run(["ydotool", "type", "--key-delay", "2", "--", text]).returncode == 0


def get_clipboard() -> bytes:
    if WAYLAND and shutil.which("wl-paste"):
        try:
            return _run(["wl-paste", "-n"], timeout=3).stdout
        except Exception:
            return b""
    if shutil.which("xclip"):
        try:
            return _run(["xclip", "-o", "-selection", "clipboard"], timeout=3).stdout
        except Exception:
            return b""
    return b""


def set_clipboard(text) -> bool:
    payload = text.encode() if isinstance(text, str) else text
    if WAYLAND and shutil.which("wl-copy"):
        return subprocess.run(["wl-copy"], input=payload, timeout=5).returncode == 0
    if shutil.which("xclip"):
        return subprocess.run(["xclip", "-selection", "clipboard"], input=payload,
                              timeout=5).returncode == 0
    return False


def _press_paste() -> bool:
    if WAYLAND and shutil.which("wtype"):
        if _run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                timeout=10).returncode == 0:
            return True
    if not WAYLAND and shutil.which("xdotool"):
        return _run(["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                    timeout=10).returncode == 0
    if shutil.which("ydotool"):
        # 29 = left ctrl, 47 = v
        return _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                    timeout=10).returncode == 0
    return False


def type_clipboard(text: str) -> bool:
    previous = get_clipboard()
    if not set_clipboard(text):
        return False
    time.sleep(0.08)
    ok = _press_paste()
    time.sleep(0.15)

    # A failed paste leaves the transcript available for manual Ctrl+V.
    # Do not delete history entries by text query: they may predate this dictation.
    if ok and previous:
        set_clipboard(previous)
    return ok


# ------------------------------------------------------------------ registry

def methods() -> dict:
    return {"wtype": type_wtype, "xdotool": type_xdotool,
            "ydotool": type_ydotool, "clipboard": type_clipboard}


def default_order() -> list[str]:
    if WAYLAND:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "kde" in desktop or "plasma" in desktop:
            return ["clipboard", "ydotool"]
        return ["wtype", "ydotool", "clipboard"]
    return ["xdotool", "ydotool", "clipboard"]


def availability() -> dict[str, bool]:
    out = {name: shutil.which(name) is not None
           for name in ("wtype", "xdotool", "ydotool", "wl-copy", "xclip")}
    out["ydotoold running"] = (shutil.which("ydotool") is not None
                               and _run(["pgrep", "-x", "ydotoold"]).returncode == 0)
    return out
