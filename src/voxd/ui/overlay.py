"""The overlay shown while dictating.

A flat capsule at the bottom of the screen: a level meter on the left, the text
on the right. No labels, no status words, no progress bar - state is carried by
what the meter is doing and by the brightness of the text.

Critical: this window must never take focus, or the injection step would type
into the overlay instead of the target field.
"""

from __future__ import annotations

import math
import sys

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Property, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QGuiApplication
from PySide6.QtWidgets import QWidget

from .theme import DARK, FONT_MD, Palette, S2, S3, S4

BARS = 14              # bars in the level meter
BAR_W = 2
BAR_GAP = 2
CAPSULE_H = 34
MAX_W = 760
MIN_W = 190


class Overlay(QWidget):
    """States: idle (hidden), listening, thinking, done, problem."""

    def __init__(self, palette: Palette = DARK):
        super().__init__(None)
        self.p = palette
        self.state = "idle"
        self.text = ""
        self.levels = [0.0] * BARS
        self._phase = 0.0
        self._fade = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool                       # no taskbar entry, no focus
            | Qt.WindowDoesNotAcceptFocus
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        self._font = QFont()
        self._font.setPixelSize(FONT_MD)
        self._fm = QFontMetrics(self._font)

        # One clock for everything that moves. 30 Hz is plenty and costs little.
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._animate)
        self._tick.setInterval(33)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

        self.resize(MIN_W, CAPSULE_H)

    # ------------------------------------------------------------ API

    def show_listening(self, text: str = ""):
        self.state = "listening"
        self.text = text
        self._hide_timer.stop()
        self._appear()

    def show_thinking(self, text: str = ""):
        self.state = "thinking"
        if text:
            self.text = text
        self._appear()

    def show_done(self, text: str, hold_ms: int = 260):
        self.state = "done"
        self.text = text
        self._appear()
        self._hide_timer.start(hold_ms)

    def show_problem(self, text: str, hold_ms: int = 2600):
        self.state = "problem"
        self.text = text
        self._appear()
        self._hide_timer.start(hold_ms)

    def push_level(self, level: float):
        """Push a new level (0..1). The meter scrolls to the left."""
        self.levels = self.levels[1:] + [max(0.0, min(1.0, level))]

    def set_text(self, text: str):
        if text != self.text:
            self.text = text
            self._relayout()

    def dismiss(self):
        self.state = "idle"
        self._tick.stop()
        self._hide_timer.stop()
        self.hide()

    # ---------------------------------------------------------- Internals

    def _appear(self):
        self._relayout()
        if not self.isVisible():
            self.show()
        if not self._tick.isActive():
            self._tick.start()

    def _relayout(self):
        meter_w = BARS * (BAR_W + BAR_GAP)
        # +2 px slack: at exactly equal widths Qt elides anyway.
        text_w = (self._fm.horizontalAdvance(self.text) + 2) if self.text else 0
        w = S4 + meter_w + S3 + text_w + S4
        w = max(MIN_W, min(MAX_W, w))

        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.resize(w, CAPSULE_H)
        self.move(geo.center().x() - w // 2, geo.bottom() - CAPSULE_H - 96)

    def _animate(self):
        self._phase += 0.16
        if self._fade < 1.0:
            self._fade = min(1.0, self._fade + 0.18)
        if self.state == "thinking":
            # No spinner. The bars settle into a slow wave - visibly still busy,
            # without anything blinking.
            self.levels = [0.12 + 0.1 * math.sin(self._phase + i * 0.5)
                           for i in range(BARS)]
        elif self.state in ("done", "problem"):
            self.levels = [v * 0.82 for v in self.levels]
        self.update()

    # ------------------------------------------------------------ Painting

    def paintEvent(self, _e):
        p = self.p
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        qp.setRenderHint(QPainter.TextAntialiasing, True)

        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(r, CAPSULE_H / 2, CAPSULE_H / 2)

        bg = QColor(p.bg)
        bg.setAlphaF(0.93 * self._fade)
        qp.fillPath(path, bg)

        border = QColor(p.line)
        border.setAlphaF(0.9 * self._fade)
        qp.strokePath(path, border)

        self._paint_meter(qp)
        self._paint_text(qp)
        qp.end()

    def _paint_meter(self, qp: QPainter):
        p = self.p
        x = S4
        mid = self.height() / 2
        base = QColor(p.accent if self.state in ("listening", "thinking")
                      else p.warn if self.state == "problem" else p.text_dim)

        for i, lv in enumerate(self.levels):
            # Square root compresses the dynamics so quiet speech stays visible.
            h = 2 + (CAPSULE_H - 16) * math.sqrt(lv)
            c = QColor(base)
            # Newer values on the right are stronger, giving the meter direction.
            c.setAlphaF((0.28 + 0.72 * (i / max(1, BARS - 1))) * self._fade)
            qp.fillRect(QRectF(x, mid - h / 2, BAR_W, h), c)
            x += BAR_W + BAR_GAP

    def _paint_text(self, qp: QPainter):
        if not self.text:
            return
        p = self.p
        x = S4 + BARS * (BAR_W + BAR_GAP) + S3
        avail = self.width() - x - S4
        # Elide from the left: the most recent words are the ones that matter.
        shown = self._fm.elidedText(self.text, Qt.ElideLeft, int(avail))

        col = QColor(p.text_dim if self.state == "listening"
                     else p.warn if self.state == "problem" else p.text)
        col.setAlphaF(self._fade)
        qp.setFont(self._font)
        qp.setPen(col)
        qp.drawText(QRectF(x, 0, avail, self.height()),
                    Qt.AlignVCenter | Qt.AlignLeft, shown)


def attach_layer_shell(win: QWidget) -> bool:
    """Register the overlay as a layer surface on wlroots compositors.

    Only there can we guarantee it stays above everything and never touches
    focus. Elsewhere Qt.Tool carries the normal case.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        from ctypes import CDLL, c_void_p, c_int
        lib = CDLL("libgtk4-layer-shell.so")   # availability probe only
        _ = lib
    except OSError:
        return False
    return False  # binding to follow; Qt.Tool covers the normal case
