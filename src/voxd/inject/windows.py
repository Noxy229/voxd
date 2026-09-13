"""Typing into other windows on Windows.

Two rungs:

  sendinput   SendInput with KEYEVENTF_UNICODE, which types arbitrary Unicode
              without caring about the keyboard layout. No administrator rights
              needed. Fails against windows running elevated — Windows blocks
              synthetic input from a lower integrity level, by design.
  clipboard   Copy and press Ctrl+V, restoring the previous clipboard after.

NOT YET TESTED ON REAL HARDWARE. Written from the documented API contracts;
until someone runs it on an actual Windows machine, treat it as unverified.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_V = 0x56
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_ubyte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("union", _INPUTunion)]


def _key_event(scan: int, flags: int, vk: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0,
                              dwExtraInfo=None)
    return inp


def _send(events: list[INPUT]) -> bool:
    if not events:
        return True
    n = len(events)
    arr = (INPUT * n)(*events)
    sent = user32.SendInput(n, arr, ctypes.sizeof(INPUT))
    return sent == n


# ------------------------------------------------------------- focused window

def focused_app() -> str:
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return "unknown"
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = wt.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value.rsplit("\\", 1)[-1] or "unknown"
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        pass
    return "unknown"


# ------------------------------------------------------------------- rungs

def type_sendinput(text: str) -> bool:
    events: list[INPUT] = []
    for ch in text:
        for unit in ch.encode("utf-16-le").decode("utf-16-le"):
            code = ord(unit)
            # Characters outside the BMP arrive as surrogate pairs; SendInput
            # takes each half as its own event.
            units = [code] if code <= 0xFFFF else [
                0xD800 + ((code - 0x10000) >> 10),
                0xDC00 + ((code - 0x10000) & 0x3FF)]
            for u in units:
                events.append(_key_event(u, KEYEVENTF_UNICODE))
                events.append(_key_event(u, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        # Send in batches so a long dictation does not build one huge array.
        if len(events) >= 400:
            if not _send(events):
                return False
            events = []
            time.sleep(0.001)
    return _send(events)


def get_clipboard() -> str:
    try:
        if not user32.OpenClipboard(None):
            return ""
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                return ctypes.c_wchar_p(ptr).value or ""
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""


def set_clipboard(text: str) -> bool:
    try:
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            data = ctypes.create_unicode_buffer(text)
            size = ctypes.sizeof(data)
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return False
            ptr = kernel32.GlobalLock(handle)
            ctypes.memmove(ptr, data, size)
            kernel32.GlobalUnlock(handle)
            return bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def type_clipboard(text: str) -> bool:
    previous = get_clipboard()
    if not set_clipboard(text):
        return False
    time.sleep(0.05)
    ok = _send([
        _key_event(0, 0, VK_CONTROL),
        _key_event(0, 0, VK_V),
        _key_event(0, KEYEVENTF_KEYUP, VK_V),
        _key_event(0, KEYEVENTF_KEYUP, VK_CONTROL),
    ])
    time.sleep(0.15)
    if previous:
        set_clipboard(previous)
    return ok


# ------------------------------------------------------------------ registry

def methods() -> dict:
    return {"sendinput": type_sendinput, "clipboard": type_clipboard}


def default_order() -> list[str]:
    return ["sendinput", "clipboard"]


def availability() -> dict[str, bool]:
    return {"sendinput": True, "clipboard": True}
