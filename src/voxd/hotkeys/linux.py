"""Shortcut registration on Linux desktops.

Every compositor wants this done differently, so each gets its own small
routine. Where voxd does not know the desktop, it says so and hands the user
the command to bind themselves — that is more useful than a silent failure.

Everything written here is fenced between marker comments so it can be removed
again cleanly, and nothing is ever appended twice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import BindResult

BEGIN_SH = "# >>> voxd shortcuts >>>"
END_SH = "# <<< voxd shortcuts <<<"
BEGIN_LUA = "-- >>> voxd shortcuts >>>"
END_LUA = "-- <<< voxd shortcuts <<<"

ACTION_ARGS = {"toggle": "toggle", "raw": "raw-toggle", "cancel": "cancel"}
ACTION_LABEL = {"toggle": "Dictate", "raw": "Dictate without editing",
                "cancel": "Discard dictation"}


def desktop() -> str:
    return (os.environ.get("XDG_CURRENT_DESKTOP")
            or os.environ.get("DESKTOP_SESSION") or "").lower()


def describe() -> str:
    d = desktop()
    if "hyprland" in d:
        return "Hyprland (written into hyprland.conf)"
    if "sway" in d:
        return "Sway (written into the sway config)"
    if "niri" in d:
        return "niri (written into config.kdl)"
    if "gnome" in d:
        return "GNOME (custom keybindings via gsettings)"
    if "kde" in d or "plasma" in d:
        return "KDE Plasma (launchers + System Settings → Keyboard → Shortcuts)"
    return f"unknown desktop ({d or 'none reported'})"


# --------------------------------------------------------------- accelerators

def _to_hypr_conf(accel: str) -> str:
    """'Super+Shift+H' -> 'SUPER SHIFT, H' for hyprland.conf's bind =."""
    parts = [p.strip().upper() for p in accel.split("+")]
    return " ".join(parts[:-1]) + ", " + parts[-1]


def _to_hypr_lua(accel: str) -> str:
    """The Lua wrappers take the whole accelerator as one string, and they
    expect the ' + ' spelling used throughout those configs."""
    return " + ".join(p.strip().upper() for p in accel.split("+"))


def _to_sway(accel: str) -> str:
    parts = [p.strip() for p in accel.split("+")]
    m = {"super": "Mod4", "ctrl": "Control", "alt": "Mod1", "shift": "Shift"}
    return "+".join(m.get(p.lower(), p) for p in parts)


def _to_gnome(accel: str) -> str:
    parts = [p.strip() for p in accel.split("+")]
    m = {"super": "<Super>", "ctrl": "<Control>", "alt": "<Alt>",
         "shift": "<Shift>"}
    out = ""
    for p in parts:
        out += m.get(p.lower(), p.lower())
    return out


# ------------------------------------------------------------ block handling

def _markers(path: Path) -> tuple[str, str]:
    return (BEGIN_LUA, END_LUA) if path.suffix == ".lua" else (BEGIN_SH, END_SH)


def _write_block(path: Path, body: str) -> None:
    """Insert or replace our fenced block, leaving the rest of the file alone."""
    BEGIN, END = _markers(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text("utf-8") if path.exists() else ""
    block = f"{BEGIN}\n{body.rstrip()}\n{END}\n"
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        text = head + block + tail.lstrip("\n")
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    tmp = path.with_suffix(path.suffix + ".voxd-tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _strip_block(path: Path) -> bool:
    if not path.exists():
        return False
    BEGIN, END = _markers(path)
    text = path.read_text("utf-8")
    if BEGIN not in text or END not in text:
        return False
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    path.write_text((head.rstrip("\n") + "\n" + tail.lstrip("\n")), "utf-8")
    return True


# -------------------------------------------------------------- per-desktop

def _hypr_path() -> Path:
    """Where this particular Hyprland setup wants user keybindings.

    Three shapes are common: a Lua-based config (end-4 and friends), a classic
    hyprland.conf with a custom/ directory that it sources, and a plain
    hyprland.conf. Writing .conf syntax into a Lua config produces a file that
    nothing reads, so the dialect has to follow the file.
    """
    hypr = Path.home() / ".config/hypr"
    lua_custom = hypr / "custom/keybinds.lua"
    if lua_custom.exists():
        return lua_custom
    if (hypr / "hyprland.lua").exists() or (hypr / "hyprland" / "keybinds.lua").exists():
        (hypr / "custom").mkdir(parents=True, exist_ok=True)
        return hypr / "custom/keybinds.lua"
    if (hypr / "custom").is_dir():
        return hypr / "custom/voxd.conf"
    return hypr / "hyprland.conf"


def _apply_hyprland(bindings, command) -> BindResult:
    path = _hypr_path()
    if path.suffix == ".lua":
        lines = [
            f'hl.bind("{_to_hypr_lua(accel)}", hl.dsp.exec_cmd("{command} '
            f'{ACTION_ARGS[action]}"), {{ description = "voxd: '
            f'{ACTION_LABEL[action]}" }})'
            for action, accel in bindings.items() if action in ACTION_ARGS]
    else:
        lines = [f"bind = {_to_hypr_conf(accel)}, exec, {command} {ACTION_ARGS[action]}"
                 for action, accel in bindings.items() if action in ACTION_ARGS]
    _write_block(path, "\n".join(lines))

    note = ""
    if path.name == "voxd.conf":
        main = Path.home() / ".config/hypr/hyprland.conf"
        sourced = main.exists() and "custom/voxd.conf" in main.read_text("utf-8")
        if not sourced:
            note = (f"Add this line to {main}:\n"
                    f"  source = ~/.config/hypr/custom/voxd.conf")
    if shutil.which("hyprctl"):
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=10)
    return BindResult(not note, f"written to {path}", note)


def _apply_sway(bindings, command) -> BindResult:
    lines = [f"bindsym {_to_sway(accel)} exec {command} {ACTION_ARGS[action]}"
             for action, accel in bindings.items() if action in ACTION_ARGS]
    path = Path(os.environ.get("SWAYSOCK") and
                Path.home() / ".config/sway/config" or
                Path.home() / ".config/sway/config")
    _write_block(path, "\n".join(lines))
    if shutil.which("swaymsg"):
        subprocess.run(["swaymsg", "reload"], capture_output=True, timeout=10)
    return BindResult(True, f"written to {path}")


def _apply_gnome(bindings, command) -> BindResult:
    if not shutil.which("gsettings"):
        return BindResult(False, "gsettings not available",
                          _manual_text(bindings, command))
    base = "org.gnome.settings-daemon.plugins.media-keys"
    prefix = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
    paths = []
    for i, (action, accel) in enumerate(
            (a, b) for a, b in bindings.items() if a in ACTION_ARGS):
        p = f"{prefix}/voxd-{action}/"
        paths.append(p)
        target = f"{base}.custom-keybinding:{p}"
        for key, val in (("name", f"voxd: {ACTION_LABEL[action]}"),
                         ("command", f"{command} {ACTION_ARGS[action]}"),
                         ("binding", _to_gnome(accel))):
            subprocess.run(["gsettings", "set", target, key, val],
                           capture_output=True, timeout=10)
    existing = subprocess.run(
        ["gsettings", "get", base, "custom-keybindings"],
        capture_output=True, text=True, timeout=10).stdout.strip()
    keep = [p for p in paths if p not in existing]
    if keep:
        merged = existing if existing.startswith("[") and existing != "@as []" else "[]"
        items = [x.strip(" '\"") for x in merged.strip("[]").split(",") if x.strip()]
        items += keep
        value = "[" + ", ".join(f"'{x}'" for x in items) + "]"
        subprocess.run(["gsettings", "set", base, "custom-keybindings", value],
                       capture_output=True, timeout=10)
    return BindResult(True, "registered as GNOME custom keybindings")


def _apply_plasma(bindings, command) -> BindResult:
    # Let KGlobalAccel handle conflict resolution through its native settings UI.
    root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    root = root / "applications"
    root.mkdir(parents=True, exist_ok=True)
    if any(c in command for c in "\n\r"):
        raise ValueError("invalid shortcut command")
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    for action in bindings:
        if action not in ACTION_ARGS:
            continue
        path = root / f"org.voxd.{action}.desktop"
        path.write_text(
            "[Desktop Entry]\nType=Application\n"
            f"Name=voxd — {ACTION_LABEL[action]}\n"
            f'Exec="{escaped}" {ACTION_ARGS[action]}\n'
            "Icon=audio-input-microphone\nTerminal=false\nCategories=Utility;\n",
            encoding="utf-8")
    updater = shutil.which("kbuildsycoca6") or shutil.which("kbuildsycoca5")
    if updater:
        subprocess.run([updater, "--noincremental"], capture_output=True, timeout=15)
    return BindResult(False, "KDE launchers installed; assign shortcuts in System Settings",
                      "Keyboard → Shortcuts → Add New → Application: search voxd.\n"
                      + _manual_text(bindings, command))


def _manual_text(bindings, command) -> str:
    rows = [f"  {accel}  →  {command} {ACTION_ARGS[action]}"
            for action, accel in bindings.items() if action in ACTION_ARGS]
    return ("Add these shortcuts in your system settings:\n" + "\n".join(rows))


# ------------------------------------------------------------------- public

def apply(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    d = desktop()
    try:
        if "hyprland" in d:
            return _apply_hyprland(bindings, command)
        if "sway" in d:
            return _apply_sway(bindings, command)
        if "kde" in d or "plasma" in d:
            return _apply_plasma(bindings, command)
        if "gnome" in d:
            return _apply_gnome(bindings, command)
    except Exception as e:
        return BindResult(False, f"could not write the binding: {e}",
                          _manual_text(bindings, command))
    return BindResult(False, f"unsupported desktop ({d or 'unknown'})",
                      _manual_text(bindings, command))


def remove(bindings: dict[str, str], command: str = "voxctl") -> BindResult:
    d = desktop()
    if "hyprland" in d:
        removed = _strip_block(_hypr_path())
        if shutil.which("hyprctl"):
            subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=10)
        return BindResult(removed, "removed" if removed else "nothing to remove")
    if "sway" in d:
        removed = _strip_block(Path.home() / ".config/sway/config")
        return BindResult(removed, "removed" if removed else "nothing to remove")
    return BindResult(False, "please remove the shortcuts by hand")
