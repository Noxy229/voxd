"""Small reusable building blocks.

Everything here defers to theme.py. No widget carries its own colours or radii -
that is how a design system falls apart.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .theme import S1, S2, S3, S4, Palette


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setTextFormat(Qt.PlainText)
    if role:
        lb.setProperty("role", role)
    lb.setWordWrap(wrap)
    if wrap:
        # Without this a word-wrapping QLabel reports too small a height and
        # gets clipped by the layout.
        lb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lb


def rule() -> QFrame:
    f = QFrame()
    f.setProperty("role", "rule")
    f.setFixedHeight(1)
    return f


def spacer(h: int = 0) -> QWidget:
    w = QWidget()
    if h:
        w.setFixedHeight(h)
    else:
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return w


class Card(QFrame):
    """A surface. Optionally clickable, in which case it emits `clicked`."""

    clicked = Signal()

    def __init__(self, selectable: bool = False):
        super().__init__()
        self.setProperty("role", "card")
        self.setProperty("selected", "false")
        self._selectable = selectable
        if selectable:
            self.setCursor(Qt.PointingHandCursor)
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(S4, S3, S4, S3)
        self.box.setSpacing(S1)

    def set_selected(self, on: bool):
        self.setProperty("selected", "true" if on else "false")
        # Qt does not re-evaluate stylesheet property selectors on its own.
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, e):
        if self._selectable and e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class KeyValue(QWidget):
    """Two columns with a fixed left column, so values line up vertically."""

    def __init__(self, key_width: int = 150):
        super().__init__()
        self.kw = key_width
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(S2)

    def add(self, key: str, value: str, value_role: str = ""):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(S3)
        k = label(key, "caption")
        k.setFixedWidth(self.kw)
        k.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        v = label(value, value_role, wrap=True)
        h.addWidget(k)
        h.addWidget(v, 1)
        self.box.addWidget(row)
        return row


class LevelMeter(QWidget):
    """Horizontal level meter - the same visual language as the overlay."""

    def __init__(self, palette: Palette, bars: int = 40):
        super().__init__()
        self.p = palette
        self.n = bars
        self.levels = [0.0] * bars
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def push(self, level: float):
        self.levels = self.levels[1:] + [max(0.0, min(1.0, level))]
        self.update()

    def reset(self):
        self.levels = [0.0] * self.n
        self.update()

    def paintEvent(self, _e):
        import math
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        w = self.width() / self.n
        mid = self.height() / 2
        for i, lv in enumerate(self.levels):
            h = max(2.0, (self.height() - 6) * math.sqrt(lv))
            c = QColor(self.p.accent if lv > 0.01 else self.p.line)
            c.setAlphaF(0.35 + 0.65 * (i / max(1, self.n - 1)))
            qp.fillRect(int(i * w), int(mid - h / 2), max(1, int(w) - 1), int(h), c)
        qp.end()


class Badge(QLabel):
    """A small tag, e.g. "measured" or "estimated"."""

    def __init__(self, text: str, palette: Palette, strong: bool = False):
        super().__init__(text)
        col = palette.accent if strong else palette.text_faint
        self.setStyleSheet(
            f"color: {col}; font-size: 11px; border: 1px solid {col};"
            f"border-radius: 3px; padding: 1px 5px;")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
