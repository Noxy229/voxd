"""Typing text into whatever window has focus.

No single method works everywhere, so this is a chain: try each rung, remember
which one worked for that application, and start there next time. The learned
map lives in the state directory, so the second dictation into a given app is
already using the right method.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


class InjectionResult:
    def __init__(self, method: str | None, app: str, error: str = ""):
        self.method = method
        self.app = app
        self.error = error

    @property
    def ok(self) -> bool:
        return self.method is not None

    def __repr__(self):
        return f"<Injection {self.method or 'failed'} into {self.app}>"


class Injector:
    """Platform-neutral front end. The rungs come from the platform module."""

    def __init__(self, cache_path: Path, order: list[str] | None = None,
                 focus_delay_ms: int = 40, log=print):
        self.cache_path = Path(cache_path)
        self.focus_delay_ms = focus_delay_ms
        self.log = log
        self._backend = _platform_backend()
        self.order = list(order or self._backend.default_order())
        self.cache = self._load_cache()

    # -- learned per-application method ---------------------------------
    def _load_cache(self) -> dict:
        try:
            data = json.loads(self.cache_path.read_text("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, indent=1), "utf-8")
        except Exception:
            pass

    def forget(self, app: str | None = None):
        """Drop what was learned — for when an app changes behaviour."""
        if app:
            self.cache.pop(app, None)
        else:
            self.cache.clear()
        self._save_cache()

    # -- the chain -------------------------------------------------------
    def inject(self, text: str) -> InjectionResult:
        if not text:
            return InjectionResult(None, "", "nothing to type")

        app = self._backend.focused_app()
        order = list(self.order)
        learned = self.cache.get(app) if app != "unknown" else None
        if learned in order:
            order.remove(learned)
            order.insert(0, learned)

        # The overlay has to be out of the way and focus settled before typing.
        time.sleep(self.focus_delay_ms / 1000)

        errors = []
        for name in order:
            fn = self._backend.methods().get(name)
            if fn is None:
                continue
            try:
                if fn(text):
                    if app != "unknown" and self.cache.get(app) != name:
                        self.cache[app] = name
                        self._save_cache()
                    self.log(f"typed via {name} into {app}")
                    return InjectionResult(name, app)
            except Exception as e:
                errors.append(f"{name}: {e}")
        return InjectionResult(None, app, "; ".join(errors) or "no method worked")

    def copy_to_clipboard(self, text: str) -> bool:
        """Last resort when nothing could type — at least do not lose the text."""
        try:
            return self._backend.set_clipboard(text)
        except Exception:
            return False

    def available(self) -> dict[str, bool]:
        return self._backend.availability()


def _platform_backend():
    if IS_WINDOWS:
        from . import windows
        return windows
    from . import linux
    return linux
