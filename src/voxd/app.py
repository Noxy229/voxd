"""The application: Qt event loop, overlay, tray, and the daemon socket.

The dictation logic lives in session.py and knows nothing about Qt. This module
is the adapter between the two — it marshals the session's callbacks onto the
Qt thread, because touching widgets from a worker thread is a reliable way to
crash.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import ipc
from .config import Config, ensure_dirs
from .session import Callbacks, Session
from .ui import theme
from .ui.overlay import Overlay


def log(*parts):
    print("[voxd]", *parts, file=sys.stderr, flush=True)


class Bridge(QObject):
    """Carries session events from worker threads onto the Qt thread."""
    state = Signal(str, str, float)
    result = Signal(object)
    command = Signal(object)


class Application:
    def __init__(self, argv: list[str]):
        ensure_dirs()
        self.cfg = Config.load()
        if self.cfg.problem:
            log(self.cfg.problem)

        self.qt = QApplication(argv)
        self.qt.setApplicationName("voxd")
        self.qt.setQuitOnLastWindowClosed(False)   # the overlay comes and goes

        self.palette = self._palette()
        self.overlay = Overlay(self.palette)

        self.bridge = Bridge()
        self.bridge.state.connect(self._on_state, Qt.QueuedConnection)
        self.bridge.result.connect(self._on_result, Qt.QueuedConnection)
        self.bridge.command.connect(self._command, Qt.QueuedConnection)

        self.session = Session(self.cfg, Callbacks(
            on_state=lambda s, t, lv: self.bridge.state.emit(s, t, lv),
            on_result=lambda r: self.bridge.result.emit(r),
            on_log=log))

        self.tray = self._build_tray()
        handlers = {name: (lambda n=name: self._dispatch(n)) for name in self._handlers()}
        self.server = ipc.Server(handlers, log=log)
        self.server.start()

        self.wizard = None
        if not self.cfg.get("setup.completed", False):
            QTimer.singleShot(0, self.open_setup)
        else:
            from .download import is_installed
            needed = [self.cfg.get("asr.model")]
            if self.cfg.get("edit.enabled"):
                needed.append(self.cfg.get("edit.model"))
            if not all(is_installed(mid) for mid in needed):
                QTimer.singleShot(0, self.open_setup)
            else:
                self.session.preload()

    # ------------------------------------------------------------- theme
    def _palette(self):
        choice = self.cfg.get("ui.theme", "system")
        if choice == "dark":
            return theme.DARK
        if choice == "light":
            return theme.LIGHT
        return theme.detect_palette()

    # -------------------------------------------------------------- tray
    def _tray_icon(self) -> QIcon:
        """Drawn rather than shipped: three bars, the same mark as the meter."""
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        qp = QPainter(pm)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setBrush(QColor(self.palette.accent))
        qp.setPen(Qt.NoPen)
        for i, h in enumerate((22, 38, 28)):
            qp.drawRoundedRect(16 + i * 12, 32 - h // 2, 6, h, 3, 3)
        qp.end()
        return QIcon(pm)

    def _build_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log("no system tray available")
            return None
        tray = QSystemTrayIcon(self._tray_icon())
        tray.setToolTip("voxd")
        menu = QMenu()

        act_toggle = QAction(f"Dictate  ({self.cfg.get('hotkeys.toggle')})", menu)
        act_toggle.triggered.connect(lambda: self.session.toggle(False))
        act_raw = QAction("Dictate without editing", menu)
        act_raw.triggered.connect(lambda: self.session.toggle(True))
        act_setup = QAction("Settings…", menu)
        act_setup.triggered.connect(self.open_setup)
        act_release = QAction("Unload models", menu)
        act_release.triggered.connect(self.session.release)
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit)

        for a in (act_toggle, act_raw):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_setup)
        menu.addAction(act_release)
        menu.addSeparator()
        menu.addAction(act_quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_clicked)
        tray.show()
        return tray

    def _tray_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.session.toggle(False)

    # ------------------------------------------------------ session events
    def _on_state(self, state: str, text: str, level: float):
        if self.overlay.tray_only:
            if self.tray:
                statuses = {"listening": "Listening", "thinking": "Processing",
                            "done": "Ready", "cancelled": "Discarded", "problem": "Needs attention"}
                self.tray.setToolTip("voxd — " + statuses.get(state, state))
                if state == "problem":
                    self.tray.showMessage("voxd", text)
            return
        if state == "listening":
            self.overlay.push_level(level)
            if not self.overlay.isVisible() or self.overlay.state != "listening":
                self.overlay.show_listening(text)
            elif text:
                self.overlay.set_text(text)
        elif state == "thinking":
            self.overlay.show_thinking(text)
        elif state == "done":
            self.overlay.show_done(text)
        elif state == "cancelled":
            self.overlay.show_problem("Discarded", hold_ms=700)
        elif state == "problem":
            self.overlay.show_problem(text)

    def _on_result(self, result):
        if result.ok and self.tray:
            self.tray.setToolTip(f"voxd — {result.total_seconds:.1f}s")

    # ------------------------------------------------------------ windows
    def open_setup(self):
        if self.session.recording or self.session.status()["busy"]:
            self.overlay.show_problem("Finish dictation before opening settings")
            return
        from .ui.wizard import Wizard
        if self.wizard is not None and self.wizard.isVisible():
            self.wizard.raise_()
            self.wizard.activateWindow()
            return
        self.wizard = Wizard(self.palette)
        self.wizard.finished.connect(self._setup_finished)
        self.wizard.closed.connect(lambda: setattr(self.session, "suspended", False))
        self.session.suspended = True
        self.wizard.show()

    def _setup_finished(self, choices: dict):
        from copy import deepcopy
        self.cfg = Config(deepcopy(self.cfg.data))
        for key, value in (("asr.model", choices.get("asr")),
                           ("asr.device", choices.get("asr_device")),
                           ("edit.model", choices.get("llm")),
                           ("edit.device", choices.get("llm_device"))):
            if value:
                self.cfg.set(key, value)
        device = choices.get("audio_device")
        self.cfg.set("audio.device", device if device is not None else "")
        self.cfg.set("edit.idle_unload_sec", 0)
        self.cfg.set("edit.enabled", bool(choices.get("llm")))
        self.cfg.set("setup.completed", True)
        self.cfg.save()
        if not self.session.reconfigure(self.cfg):
            self.overlay.show_problem("Models still loading; restart voxd to apply settings")
        if self.wizard:
            self.wizard.close()
        import shutil

        from . import hotkeys
        command = shutil.which("voxctl") or "voxctl"
        bindings = {key: self.cfg.get(f"hotkeys.{key}") for key in ("toggle", "raw", "cancel")}
        result = hotkeys.apply(bindings, command)
        if not result.ok:
            log(result.how, result.manual_hint)
            if self.tray:
                self.tray.showMessage("Shortcut setup", result.how + "\n" + result.manual_hint)

    # ---------------------------------------------------------- lifecycle
    def _dispatch(self, name):
        request = {"name": name, "done": threading.Event(), "reply": "error: timed out"}
        self.bridge.command.emit(request)
        if not request["done"].wait(10):
            request["done"].set()
        return request["reply"]

    def _command(self, request):
        if request["done"].is_set():
            return
        try:
            request["reply"] = self._handlers()[request["name"]]()
        except Exception as e:
            request["reply"] = f"error: {e}"
        finally:
            request["done"].set()

    def _handlers(self) -> dict:
        return {
            "toggle": lambda: (self.session.toggle(False), "ok")[1],
            "raw-toggle": lambda: (self.session.toggle(True), "ok")[1],
            "start": lambda: (self.session.start(False), "ok")[1],
            "stop": lambda: (self.session.stop(), "ok")[1],
            "cancel": lambda: (self.session.cancel(), "ok")[1],
            "insert-raw": lambda: (self.session.insert_last_raw(), "ok")[1],
            "release": lambda: "ok" if self.session.release() else "busy",
            "status": self.session.status,
            "reload": self.reload,
            "setup": lambda: (self.open_setup(), "ok")[1],
            "quit": lambda: (QTimer.singleShot(0, self.quit), "ok")[1],
        }

    def reload(self) -> str:
        cfg = Config.load()
        if cfg.problem:
            return cfg.problem
        if not self.session.reconfigure(cfg):
            return "busy: finish dictation/model loading before reload"
        self.cfg = cfg
        return "ok"

    def quit(self):
        self.server.stop()
        self.session.close()
        self.qt.quit()

    def run(self) -> int:
        return self.qt.exec()
