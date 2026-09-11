"""First-run setup.

Seven steps, no terminal required. The structure is deliberately plain: a step
counter, a heading, the content, a footer. No icon rail, no progress beads —
that would be decoration without information.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import catalog, hardware
from .theme import DARK, Palette, S2, S3, S4, S5, S6, stylesheet
from .widgets import Badge, Card, KeyValue, LevelMeter, label, rule, spacer

PKG_HINTS = {
    "pacman": "sudo pacman -S --needed {}",
    "apt": "sudo apt install -y {}",
    "dnf": "sudo dnf install -y {}",
    "zypper": "sudo zypper install -y {}",
    "apk": "sudo apk add {}",
}

# Package names differ between distributions.
PKG_NAMES = {
    "pacman": {"wtype": "wtype", "ydotool": "ydotool", "wl-copy": "wl-clipboard",
               "xdotool": "xdotool", "portaudio": "portaudio"},
    "apt": {"wtype": "wtype", "ydotool": "ydotool", "wl-copy": "wl-clipboard",
            "xdotool": "xdotool", "portaudio": "libportaudio2"},
    "dnf": {"wtype": "wtype", "ydotool": "ydotool", "wl-copy": "wl-clipboard",
            "xdotool": "xdotool", "portaudio": "portaudio"},
    "zypper": {"wtype": "wtype", "ydotool": "ydotool", "wl-copy": "wl-clipboard",
               "xdotool": "xdotool", "portaudio": "portaudio"},
    "apk": {"wtype": "wtype", "ydotool": "ydotool", "wl-copy": "wl-clipboard",
            "xdotool": "xdotool", "portaudio": "portaudio"},
}


class Step(QWidget):
    """One page. Subclasses fill `body` and set `title` / `lead`."""

    changed = Signal()

    title = ""
    lead = ""

    def __init__(self, wiz: "Wizard"):
        super().__init__()
        self.wiz = wiz
        self.p = wiz.p

        # Content lives in a scroll area. It only becomes visible when a page
        # outgrows the window, so it never draws attention to itself.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        root = QVBoxLayout(inner)
        root.setContentsMargins(S6, S5, S6, S4)
        root.setSpacing(0)

        root.addWidget(label(self.title, "title"))
        if self.lead:
            root.addWidget(spacer(S2))
            lead = label(self.lead, "lead", wrap=True)
            lead.setMaximumWidth(560)
            root.addWidget(lead)
        root.addWidget(spacer(S5))

        self.body = QVBoxLayout()
        self.body.setSpacing(S3)
        root.addLayout(self.body)
        root.addWidget(spacer())
        self.build()

    def build(self):
        ...

    def can_advance(self) -> bool:
        return True

    def on_enter(self):
        ...

    def on_leave(self):
        ...


# ----------------------------------------------------------------- 1 Welcome

class WelcomeStep(Step):
    title = "voxd"
    lead = ("Dictation that understands corrections. Press a key, speak, and the "
            "text lands in the field — none of it leaves this machine.")

    def build(self):
        c = Card()
        c.box.setSpacing(S3)
        c.box.addWidget(label("You can correct yourself mid-sentence:", "caption"))

        for spoken, written in (
            ("“…that the meeting is on Tuesday. No, Wednesday. "
             "Wednesday at three.”",
             "The meeting is on Wednesday at three."),
            ("“The docs for the deployment script, actually no, scratch "
             "that, the docs for the CI pipeline.”",
             "I need the docs for the CI pipeline."),
        ):
            row = QVBoxLayout()
            row.setSpacing(2)
            row.addWidget(label(spoken, "caption", wrap=True))
            row.addWidget(label(written, "", wrap=True))
            c.box.addLayout(row)
        self.body.addWidget(c)
        self.body.addWidget(label(
            "Setup takes a few minutes. Everything here can be changed later.",
            "caption", wrap=True))


# ---------------------------------------------------------------- 2 Hardware

class HardwareStep(Step):
    title = "What is in this machine"
    lead = "The recommendation on the next page follows from this."

    def build(self):
        c = Card()
        kv = KeyValue(160)
        for k, v in self.wiz.machine.summary():
            kv.add(k, v)
        c.box.addWidget(kv)
        self.body.addWidget(c)


# ----------------------------------------------------------- 3 Recommendation

class RecommendStep(Step):
    title = "Recommendation"
    lead = ""

    def build(self):
        rec = self.wiz.rec
        self.wiz.choice = "recommended"

        main = Card(selectable=True)
        main.set_selected(True)
        main.box.setSpacing(S2)

        head = QHBoxLayout()
        head.addWidget(label("Recommended", "section"))
        head.addStretch(1)
        head.addWidget(label(f"{rec.total_mb / 1024:.1f} GB download", "caption"))
        main.box.addLayout(head)

        main.box.addWidget(label(rec.asr.title))
        main.box.addWidget(label(rec.asr.blurb, "caption", wrap=True))
        if rec.asr.measured_on:
            row = QHBoxLayout()
            row.setSpacing(S2)
            row.addWidget(Badge("measured", self.p, strong=True))
            row.addWidget(label(rec.asr.measured_on, "mono"), 1)
            main.box.addLayout(row)

        main.box.addWidget(spacer(S2))
        if rec.llm:
            where = "graphics card" if rec.llm_device == "gpu" else "processor"
            main.box.addWidget(label(
                f"{rec.llm.title} — self-correction, on the {where}"))
            main.box.addWidget(label(rec.llm.blurb, "caption", wrap=True))
        else:
            main.box.addWidget(label("No language model", ""))
            main.box.addWidget(label(
                "Self-correction would need an extra model, and this machine is "
                "too tight for one. Punctuation still works — the recogniser "
                "does that itself.", "caption", wrap=True))

        self.body.addWidget(main)
        self.body.addWidget(label(rec.reason, "caption", wrap=True))

        if rec.alternatives:
            self.body.addWidget(spacer(S2))
            self.body.addWidget(label("Alternative", "section"))
            for alt in rec.alternatives:
                a = Card(selectable=True)
                a.box.setSpacing(2)
                a.box.addWidget(label(alt.title))
                a.box.addWidget(label(alt.blurb, "caption", wrap=True))
                if alt.measured_on:
                    a.box.addWidget(label(alt.measured_on, "mono"))
                self._wire(main, a, alt)
                self.body.addWidget(a)

    def _wire(self, main: Card, alt: Card, model):
        def pick_alt():
            main.set_selected(False)
            alt.set_selected(True)
            self.wiz.choice = model.id

        def pick_main():
            alt.set_selected(False)
            main.set_selected(True)
            self.wiz.choice = "recommended"

        alt.clicked.connect(pick_alt)
        main.clicked.connect(pick_main)


# ------------------------------------------------------------ 4 Dependencies

class DepsStep(Step):
    title = "System components"
    lead = ("voxd needs a few operating-system tools to be able to type into "
            "other applications' windows.")

    def build(self):
        import shutil
        sysinfo = self.wiz.machine.system
        mgr = sysinfo.get("package_manager")
        wayland = sysinfo.get("session") == "wayland"

        needed = [("wl-copy", "Clipboard", True)]
        if wayland:
            needed += [("wtype", "Typing (Wayland)", True),
                       ("ydotool", "Fallback", False)]
        else:
            needed += [("xdotool", "Typing (X11)", True)]

        missing = []
        c = Card()
        kv = KeyValue(160)
        for binary, purpose, required in needed:
            ok = shutil.which(binary) is not None
            kv.add(purpose, f"{binary} — {'present' if ok else 'missing'}",
                   "" if ok else "warn")
            if not ok and required:
                missing.append(binary)
        c.box.addWidget(kv)
        self.body.addWidget(c)

        if not missing:
            self.body.addWidget(label("All present. Nothing to do.", "caption"))
            return

        names = [PKG_NAMES.get(mgr, {}).get(b, b) for b in missing]
        if mgr and mgr in PKG_HINTS:
            cmd = PKG_HINTS[mgr].format(" ".join(names))
            self.body.addWidget(label("Install them with:", "caption"))
            box = Card()
            box.box.addWidget(label(cmd, "mono", wrap=True))
            self.body.addWidget(box)
        else:
            self.body.addWidget(label(
                "Package manager not recognised. Please install: "
                + ", ".join(names), "warn", wrap=True))
        self.body.addWidget(label(
            "You can continue without them — dictated text then lands in the "
            "clipboard instead of directly in the field.", "caption", wrap=True))


# ------------------------------------------------------------- 5 Microphone

class MicStep(Step):
    title = "Microphone"
    lead = ("Say a sentence and watch the meter move. A dead microphone is the "
            "single most common reason dictation does not work.")

    def build(self):
        self.combo = QComboBox()
        self.devices = self.wiz.list_inputs()
        for d in self.devices:
            self.combo.addItem(d["label"], d["id"])
        self.body.addWidget(self.combo)

        c = Card()
        self.meter = LevelMeter(self.p)
        c.box.addWidget(self.meter)
        self.body.addWidget(c)

        row = QHBoxLayout()
        self.test_btn = QPushButton("Record five seconds and check")
        self.test_btn.clicked.connect(self._test)
        row.addWidget(self.test_btn)
        row.addStretch(1)
        self.body.addLayout(row)

        self.result = label("", "caption", wrap=True)
        self.body.addWidget(self.result)

    def on_enter(self):
        self.wiz.start_monitor(self.combo.currentData(), self.meter)
        self.combo.currentIndexChanged.connect(self._switch)

    def on_leave(self):
        self.wiz.stop_monitor()

    def _switch(self):
        self.wiz.start_monitor(self.combo.currentData(), self.meter)

    def _test(self):
        self.test_btn.setEnabled(False)
        self.result.setText("Recording…")
        self.wiz.run_mic_test(self.combo.currentData(), self._done)

    def _done(self, ok: bool, message: str):
        self.test_btn.setEnabled(True)
        self.result.setProperty("role", "caption" if ok else "warn")
        self.result.setText(message)
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)


# ---------------------------------------------------------------- 6 Shortcut

class HotkeyStep(Step):
    title = "Keyboard shortcut"
    lead = ""

    def build(self):
        sysinfo = self.wiz.machine.system
        c = Card()
        c.box.addWidget(label("Start and stop dictation", "caption"))
        c.box.addWidget(label(self.wiz.hotkey_label, "title"))
        self.body.addWidget(c)

        desktop = (sysinfo.get("desktop") or "").lower()
        if sysinfo.get("os") == "windows":
            note = ("Registered directly with Windows. If another program has "
                    "already claimed the combination, voxd will say so.")
        elif any(k in desktop for k in ("hyprland", "sway", "river", "niri")):
            note = (f"Written into your {desktop.title()} configuration as a key "
                    "binding. On Wayland that is the only reliable route — the "
                    "protocol does not let an application grab global keys.")
        elif "gnome" in desktop or "kde" in desktop or "plasma" in desktop:
            note = ("Added as a custom shortcut in your system settings. If that "
                    "does not take, you can bind it there yourself to the "
                    "command: voxctl toggle")
        else:
            note = ("Your desktop environment is not one voxd knows. Please add "
                    "the shortcut yourself in the system settings, bound to the "
                    "command: voxctl toggle")
        self.body.addWidget(label(note, "caption", wrap=True))


# ---------------------------------------------------------------- 7 Download

class DownloadStep(Step):
    title = "Download models"
    lead = ""

    def build(self):
        self.card = Card()
        self.rows = KeyValue(260)
        self.card.box.addWidget(self.rows)
        self.body.addWidget(self.card)
        self.status = label("", "caption", wrap=True)
        self.body.addWidget(self.status)

    def on_enter(self):
        rec = self.wiz.rec
        models = [m for m in (rec.asr, rec.llm) if m]
        total = sum(m.size_mb for m in models)
        for m in models:
            self.rows.add(m.title, f"{m.size_mb / 1024:.1f} GB")
        self.status.setText(f"{total / 1024:.1f} GB in total. The download starts "
                            "when you press Finish.")


STEPS = [WelcomeStep, HardwareStep, RecommendStep, DepsStep, MicStep,
         HotkeyStep, DownloadStep]


# ------------------------------------------------------------------- Shell

class Wizard(QWidget):
    finished = Signal(dict)

    def __init__(self, palette: Palette = DARK, machine=None):
        super().__init__()
        self.p = palette
        self.machine = machine or hardware.detect()
        self.rec = catalog.recommend(self.machine)
        self.choice = "recommended"
        self.hotkey_label = ("Win + H" if self.machine.system.get("os") == "windows"
                             else "Super + H")
        self._monitor = None

        self.setObjectName("root")
        self.setWindowTitle("Set up voxd")
        self.setStyleSheet(stylesheet(palette))
        self.resize(720, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header: the step counter and nothing else.
        head = QWidget()
        hb = QHBoxLayout(head)
        hb.setContentsMargins(S6, S4, S6, 0)
        self.step_label = label("", "caption")
        hb.addWidget(self.step_label)
        hb.addStretch(1)
        root.addWidget(head)

        self.stack = QStackedWidget()
        for cls in STEPS:
            self.stack.addWidget(cls(self))
        root.addWidget(self.stack, 1)

        root.addWidget(rule())
        foot = QWidget()
        fb = QHBoxLayout(foot)
        fb.setContentsMargins(S6, S3, S6, S4)
        fb.setSpacing(S2)
        self.back_btn = QPushButton("Back")
        self.back_btn.setProperty("role", "quiet")
        self.back_btn.clicked.connect(self.back)
        self.next_btn = QPushButton("Continue")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.setDefault(True)
        self.next_btn.clicked.connect(self.next)
        fb.addWidget(self.back_btn)
        fb.addStretch(1)
        fb.addWidget(self.next_btn)
        root.addWidget(foot)

        self._sync()

    # -- Navigation ------------------------------------------------------
    def _sync(self):
        i = self.stack.currentIndex()
        self.step_label.setText(f"Step {i + 1} of {len(STEPS)}")
        self.back_btn.setVisible(i > 0)
        self.next_btn.setText("Finish" if i == len(STEPS) - 1 else "Continue")
        self.stack.currentWidget().on_enter()

    def next(self):
        cur = self.stack.currentWidget()
        if not cur.can_advance():
            return
        cur.on_leave()
        if self.stack.currentIndex() == len(STEPS) - 1:
            self.finished.emit(self.result())
            return
        self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self._sync()

    def back(self):
        self.stack.currentWidget().on_leave()
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync()

    def result(self) -> dict:
        asr = self.rec.asr if self.choice == "recommended" else catalog.get(self.choice)
        return {"asr": asr.id if asr else None,
                "asr_device": self.rec.asr_device,
                "llm": self.rec.llm.id if self.rec.llm else None,
                "llm_device": self.rec.llm_device,
                "hotkey": self.hotkey_label}

    # -- Hooks the application provides ----------------------------------
    def list_inputs(self) -> list[dict]:
        from ..audio import list_input_devices
        return list_input_devices()

    def start_monitor(self, device_id, meter):
        self.stop_monitor()
        from ..audio import LevelMonitor
        self._monitor = LevelMonitor(device_id, meter.push)
        self._monitor.start()

    def stop_monitor(self):
        if self._monitor:
            self._monitor.stop()
            self._monitor = None

    def run_mic_test(self, device_id, callback):
        from ..audio import quick_test
        quick_test(device_id, callback)
