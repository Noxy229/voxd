"""Einrichtung beim ersten Start.

Sieben Schritte, kein Terminal. Der Aufbau ist bewusst schlicht: eine
Schrittangabe, eine Ueberschrift, ein Inhalt, eine Fusszeile. Keine Seitenleiste
mit Symbolen, keine Fortschrittsperlen - das waere Dekoration ohne Nutzen.
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

# Paketnamen unterscheiden sich je Distribution.
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
    """Eine Seite. Unterklassen fuellen `body` und setzen Titel und Vorspann."""

    changed = Signal()

    title = ""
    lead = ""

    def __init__(self, wiz: "Wizard"):
        super().__init__()
        self.wiz = wiz
        self.p = wiz.p

        # Der Inhalt liegt in einem Rollbereich. Sichtbar wird der nur, wenn
        # eine Seite laenger wird als das Fenster - sonst faellt er nicht auf.
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


# --------------------------------------------------------------- 1 Willkommen

class WelcomeStep(Step):
    title = "voxd"
    lead = ("Diktieren mit Selbstkorrektur. Taste drücken, sprechen, der Text "
            "steht im Feld — nichts davon verlässt diesen Rechner.")

    def build(self):
        c = Card()
        c.box.setSpacing(S3)
        c.box.addWidget(label("Du darfst Dich mitten im Satz korrigieren:", "caption"))

        for spoken, written in (
            ("\u201e\u2026dass das Meeting am Dienstag stattfindet. Nee, Mittwoch. "
             "Mittwoch um drei.\u201c",
             "Das Meeting findet am Mittwoch um drei Uhr statt."),
            ("\u201eDie Doku f\u00fcrs Deployment-Skript, ach nee, streich das, "
             "die Doku f\u00fcr die CI-Pipeline.\u201c",
             "Ich brauche die Doku f\u00fcr die CI-Pipeline."),
        ):
            row = QVBoxLayout()
            row.setSpacing(2)
            row.addWidget(label(spoken, "caption", wrap=True))
            row.addWidget(label(written, "", wrap=True))
            c.box.addLayout(row)
        self.body.addWidget(c)
        self.body.addWidget(label(
            "Die Einrichtung dauert wenige Minuten. Du kannst alles später ändern.",
            "caption", wrap=True))


# ---------------------------------------------------------------- 2 Hardware

class HardwareStep(Step):
    title = "Was in diesem Rechner steckt"
    lead = "Danach richtet sich die Empfehlung im nächsten Schritt."

    def build(self):
        c = Card()
        kv = KeyValue(160)
        for k, v in self.wiz.machine.summary():
            kv.add(k, v)
        c.box.addWidget(kv)
        self.body.addWidget(c)


# -------------------------------------------------------------- 3 Empfehlung

class RecommendStep(Step):
    title = "Vorschlag"
    lead = ""

    def build(self):
        rec = self.wiz.rec
        self.wiz.choice = "recommended"

        main = Card(selectable=True)
        main.set_selected(True)
        main.box.setSpacing(S2)

        head = QHBoxLayout()
        head.addWidget(label("Empfohlen", "section"))
        head.addStretch(1)
        head.addWidget(label(f"{rec.total_mb / 1024:.1f} GB Download", "caption"))
        main.box.addLayout(head)

        main.box.addWidget(label(rec.asr.title))
        main.box.addWidget(label(rec.asr.blurb, "caption", wrap=True))
        if rec.asr.measured_on:
            row = QHBoxLayout()
            row.setSpacing(S2)
            row.addWidget(Badge("gemessen", self.p, strong=True))
            row.addWidget(label(rec.asr.measured_on, "mono"), 1)
            main.box.addLayout(row)

        main.box.addWidget(spacer(S2))
        if rec.llm:
            main.box.addWidget(label(
                f"{rec.llm.title} — Selbstkorrektur "
                f"({'Grafikkarte' if rec.llm_device == 'gpu' else 'Prozessor'})"))
            main.box.addWidget(label(rec.llm.blurb, "caption", wrap=True))
        else:
            main.box.addWidget(label("Ohne Sprachmodell", ""))
            main.box.addWidget(label(
                "Für die Selbstkorrektur wäre ein zusätzliches Modell nötig; dieser "
                "Rechner ist dafür zu knapp. Satzzeichen setzt die Spracherkennung "
                "selbst.", "caption", wrap=True))

        self.body.addWidget(main)
        self.body.addWidget(label(rec.reason, "caption", wrap=True))

        if rec.alternatives:
            self.body.addWidget(spacer(S2))
            self.body.addWidget(label("Andere Möglichkeit", "section"))
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


# ------------------------------------------------------------ 4 Systemteile

class DepsStep(Step):
    title = "Systemteile"
    lead = ("voxd braucht ein paar Programme des Betriebssystems, um Text in "
            "fremde Fenster schreiben zu können.")

    def build(self):
        import shutil
        sysinfo = self.wiz.machine.system
        mgr = sysinfo.get("package_manager")
        wayland = sysinfo.get("session") == "wayland"

        needed = [("wl-copy", "Zwischenablage", True)]
        if wayland:
            needed += [("wtype", "Text tippen (Wayland)", True),
                       ("ydotool", "Rückfallebene", False)]
        else:
            needed += [("xdotool", "Text tippen (X11)", True)]

        missing = []
        c = Card()
        kv = KeyValue(160)
        for binary, purpose, required in needed:
            ok = shutil.which(binary) is not None
            kv.add(purpose, f"{binary} — {'vorhanden' if ok else 'fehlt'}",
                   "" if ok else "warn")
            if not ok and required:
                missing.append(binary)
        c.box.addWidget(kv)
        self.body.addWidget(c)

        if not missing:
            self.body.addWidget(label("Alles da. Nichts zu tun.", "caption"))
            return

        names = [PKG_NAMES.get(mgr, {}).get(b, b) for b in missing]
        if mgr and mgr in PKG_HINTS:
            cmd = PKG_HINTS[mgr].format(" ".join(names))
            self.body.addWidget(label("So installierst Du sie:", "caption"))
            box = Card()
            box.box.addWidget(label(cmd, "mono", wrap=True))
            self.body.addWidget(box)
        else:
            self.body.addWidget(label(
                "Paketverwaltung nicht erkannt. Bitte installiere: "
                + ", ".join(names), "warn", wrap=True))
        self.body.addWidget(label(
            "Du kannst auch ohne weitermachen — dann landet der Text in der "
            "Zwischenablage statt direkt im Feld.", "caption", wrap=True))


# ------------------------------------------------------------- 5 Mikrofon

class MicStep(Step):
    title = "Mikrofon"
    lead = ("Sprich einen Satz und sieh nach, ob der Ausschlag mitgeht. Ein "
            "totes Mikrofon ist der häufigste Grund, warum Diktieren nicht "
            "funktioniert.")

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
        self.test_btn = QPushButton("Fünf Sekunden aufnehmen und prüfen")
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
        self.result.setText("Läuft…")
        self.wiz.run_mic_test(self.combo.currentData(), self._done)

    def _done(self, ok: bool, message: str):
        self.test_btn.setEnabled(True)
        self.result.setProperty("role", "caption" if ok else "warn")
        self.result.setText(message)
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)


# --------------------------------------------------------- 6 Tastenkuerzel

class HotkeyStep(Step):
    title = "Tastenkombination"
    lead = ""

    def build(self):
        sysinfo = self.wiz.machine.system
        c = Card()
        c.box.addWidget(label("Diktat starten und beenden", "caption"))
        c.box.addWidget(label(self.wiz.hotkey_label, "title"))
        self.body.addWidget(c)

        desktop = (sysinfo.get("desktop") or "").lower()
        if sysinfo.get("os") == "windows":
            note = ("Wird direkt bei Windows angemeldet. Falls ein anderes Programm "
                    "die Kombination schon belegt, sagt voxd Bescheid.")
        elif any(k in desktop for k in ("hyprland", "sway", "river", "niri")):
            note = (f"Wird als Tastenbindung in Deiner {desktop.title()}-Konfiguration "
                    "eingetragen. Das ist der zuverlässigste Weg unter Wayland.")
        elif "gnome" in desktop or "kde" in desktop or "plasma" in desktop:
            note = ("Wird in den Systemeinstellungen als eigene Tastenbindung angelegt. "
                    "Sollte das nicht durchgehen, kannst Du sie dort selbst auf "
                    "„voxctl toggle“ legen.")
        else:
            note = ("Deine Oberfläche kenne ich nicht. Lege die Kombination bitte "
                    "selbst in den Systemeinstellungen an, Befehl: voxctl toggle")
        self.body.addWidget(label(note, "caption", wrap=True))


# ------------------------------------------------------------------ 7 Laden

class DownloadStep(Step):
    title = "Modelle laden"
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
        self.status.setText(f"Zusammen {total / 1024:.1f} GB. "
                            "Der Download startet, sobald Du auf Fertigstellen klickst.")


STEPS = [WelcomeStep, HardwareStep, RecommendStep, DepsStep, MicStep,
         HotkeyStep, DownloadStep]


# ------------------------------------------------------------------ Rahmen

class Wizard(QWidget):
    finished = Signal(dict)

    def __init__(self, palette: Palette = DARK, machine=None):
        super().__init__()
        self.p = palette
        self.machine = machine or hardware.detect()
        self.rec = catalog.recommend(self.machine)
        self.choice = "recommended"
        self.hotkey_label = ("Windows + H" if self.machine.system.get("os") == "windows"
                             else "Super + H")
        self._monitor = None

        self.setObjectName("root")
        self.setWindowTitle("voxd einrichten")
        self.setStyleSheet(stylesheet(palette))
        self.resize(720, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Kopf: nur die Schrittangabe, sonst nichts.
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
        self.back_btn = QPushButton("Zurück")
        self.back_btn.setProperty("role", "quiet")
        self.back_btn.clicked.connect(self.back)
        self.next_btn = QPushButton("Weiter")
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
        self.step_label.setText(f"Schritt {i + 1} von {len(STEPS)}")
        self.back_btn.setVisible(i > 0)
        self.next_btn.setText("Fertigstellen" if i == len(STEPS) - 1 else "Weiter")
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

    # -- Haken, die die Anwendung setzt ----------------------------------
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
