"""Settings and on-disk locations.

One TOML file, written atomically. Defaults live here so a missing or damaged
config never stops the program from starting — it falls back and says so.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:                     # Python 3.10
    import tomli as tomllib  # type: ignore

IS_WINDOWS = sys.platform == "win32"


# ----------------------------------------------------------------- locations

def _base(kind: str) -> Path:
    if IS_WINDOWS:
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
        return root / "voxd" / kind
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/voxd" / kind
    env = {"config": "XDG_CONFIG_HOME", "data": "XDG_DATA_HOME",
           "state": "XDG_STATE_HOME", "cache": "XDG_CACHE_HOME"}[kind]
    default = {"config": ".config", "data": ".local/share",
               "state": ".local/state", "cache": ".cache"}[kind]
    return Path(os.environ.get(env) or Path.home() / default) / "voxd"


CONFIG_DIR = _base("config")
DATA_DIR = _base("data")
STATE_DIR = _base("state")
MODEL_DIR = DATA_DIR / "models"
CONFIG_PATH = CONFIG_DIR / "config.toml"
INJECT_CACHE = STATE_DIR / "inject-cache.json"
LOG_PATH = STATE_DIR / "voxd.log"


def runtime_dir() -> Path:
    if IS_WINDOWS:
        return Path(tempfile.gettempdir()) / "voxd"
    rt = os.environ.get("XDG_RUNTIME_DIR")
    return Path(rt) / "voxd" if rt else Path(tempfile.gettempdir()) / f"voxd-{os.getuid()}"


def ensure_dirs():
    for d in (CONFIG_DIR, DATA_DIR, STATE_DIR, MODEL_DIR, runtime_dir()):
        d.mkdir(parents=True, exist_ok=True)


def model_path(model_id: str) -> Path:
    return MODEL_DIR / model_id


# ------------------------------------------------------------------ defaults

DEFAULTS: dict = {
    "setup": {
        "completed": False,
        "version": 2,
    },
    "audio": {
        "device": "",               # empty = system default
    },
    "asr": {
        "model": "parakeet-tdt-0.6b-v3-int8",
        "device": "cpu",            # cpu | gpu
        "language": "auto",         # only whisper honours this
        "threads": 0,               # 0 = choose automatically
    },
    "edit": {
        "enabled": True,
        # minimal  - self-corrections and punctuation only
        # moderate - also removes filler words
        # strong   - also smooths into clean written prose
        "level": "strong",
        "model": "qwen3-1.7b-q4_k_m",
        "device": "cpu",
        "port": 8612,
        "idle_unload_sec": 0,  # 0 = stay resident until explicitly unloaded
        # Safety net: if the edited text drifts too far in length from what was
        # actually said, the raw transcript is used instead.
        "max_growth": 2.5,
        "min_shrink": 0.3,
    },
    "hotkeys": {
        "toggle": "Super+H",
        "raw": "Super+Shift+H",
        "cancel": "Super+Alt+H",
    },
    "inject": {
        "focus_delay_ms": 40,
        "order": [],             # platform/session-specific default
    },
    "ui": {
        "theme": "system",          # system | dark | light
        "live_preview": True,
    },
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# -------------------------------------------------------------------- config

@dataclass
class Config:
    data: dict = field(default_factory=lambda: _deep_merge(DEFAULTS, {}))
    problem: str = ""               # non-empty if the file could not be read

    # -- access --------------------------------------------------------
    def get(self, path: str, default=None):
        """cfg.get("edit.level") — dotted lookup, never raises."""
        node = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value):
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    # -- persistence ---------------------------------------------------
    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if not CONFIG_PATH.exists():
            return cfg
        try:
            saved = tomllib.loads(CONFIG_PATH.read_text("utf-8"))
            if saved.get("setup", {}).get("version", 1) < 2:
                editor = saved.get("edit", {})
                if editor.get("model") == "qwen3-4b-q5_k_m":
                    editor.update(model="qwen3-1.7b-q4_k_m", device="cpu")
                if editor.get("idle_unload_sec") == 90:
                    editor["idle_unload_sec"] = 0
                saved.setdefault("setup", {})["version"] = 2
            cfg.data = _deep_merge(DEFAULTS, saved)
        except Exception as e:
            cfg.problem = f"{CONFIG_PATH} could not be read ({e}); using defaults"
        return cfg

    def save(self):
        """Write via a temporary file and replace, so an interrupted write
        cannot leave a half-written config behind."""
        ensure_dirs()
        text = _dump(self.data)
        tmp = CONFIG_PATH.with_suffix(".toml.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, CONFIG_PATH)


def _dump(data: dict, prefix: str = "") -> str:
    """Minimal TOML writer — avoids a dependency for a handful of scalars."""
    scalars, tables = [], []
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        else:
            scalars.append((k, v))

    out = []
    if prefix and scalars:
        out.append(f"[{prefix}]")
    for k, v in scalars:
        out.append(f"{k} = {_val(v)}")
    if scalars:
        out.append("")
    for k, v in tables:
        out.append(_dump(v, f"{prefix}.{k}" if prefix else k))
    return "\n".join(out)


def _val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)
