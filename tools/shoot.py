#!/usr/bin/env python3
"""Render the product images used in the README.

Everything is drawn offscreen from the real widgets, so the screenshots can
never drift away from the actual interface and never capture anything from a
developer's desktop. Run with:  QT_QPA_PLATFORM=offscreen python tools/shoot.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QRectF, Qt                                  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QImage, QPainter, QPainterPath,  # noqa: E402
                           QLinearGradient)
from PySide6.QtWidgets import QApplication                             # noqa: E402

from voxd.ui import theme                                              # noqa: E402
from voxd.ui.overlay import CAPSULE_H, Overlay                         # noqa: E402
from voxd.ui.wizard import STEPS, Wizard                               # noqa: E402

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

DOC_LINES = [
    ("Subject: Moving the review", "head"),
    ("", ""),
    ("Hi Maya,", ""),
    ("", ""),
    ("thanks for the quick reply. I would like to move the review", ""),
    ("of the first milestone by one week so we can close out the", ""),
    ("open items from the test run beforehand.", ""),
]


def speech_levels(n: int, seed: int = 3) -> list[float]:
    """A plausible speech envelope rather than random noise."""
    random.seed(seed)
    out = []
    for i in range(n):
        env = 0.52 + 0.40 * math.sin(i * 0.55) + 0.13 * math.sin(i * 1.9)
        out.append(max(0.05, min(1.0, env * random.uniform(0.72, 1.12))))
    return out


def overlay_image(state: str, text: str, pal, seed: int = 3) -> QImage:
    ov = Overlay(pal)
    ov.state, ov.text, ov._fade = state, text, 1.0
    if state == "thinking":
        ov.levels = [0.12 + 0.1 * math.sin(i * 0.5) for i in range(len(ov.levels))]
    elif state in ("problem",):
        ov.levels = [0.0] * len(ov.levels)
    else:
        ov.levels = speech_levels(len(ov.levels), seed)
    ov._relayout()
    ov.resize(ov.width(), CAPSULE_H)
    return ov.grab().toImage()


def rounded(qp: QPainter, rect: QRectF, r: float, fill: QColor, border: QColor | None = None):
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    qp.fillPath(path, fill)
    if border:
        qp.strokePath(path, border)


# ------------------------------------------------------------------- hero

def hero(pal, name: str):
    """The overlay sitting over a document, as it appears in use."""
    W, H = 1280, 640
    img = QImage(W, H, QImage.Format_ARGB32)
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing)
    qp.setRenderHint(QPainter.TextAntialiasing)

    # Backdrop: a quiet vertical wash, no decorative shapes.
    g = QLinearGradient(0, 0, 0, H)
    if pal is theme.DARK:
        g.setColorAt(0.0, QColor("#0C0C0E"))
        g.setColorAt(1.0, QColor("#141418"))
    else:
        g.setColorAt(0.0, QColor("#EFEFEA"))
        g.setColorAt(1.0, QColor("#E3E3DC"))
    qp.fillRect(0, 0, W, H, g)

    # The window being dictated into.
    win = QRectF(140, 66, W - 280, 424)
    rounded(qp, win, 10, QColor(pal.surface), QColor(pal.line))

    # Title bar: three dots, nothing else.
    qp.setPen(Qt.NoPen)
    for i, _ in enumerate(range(3)):
        c = QColor(pal.text_faint)
        c.setAlphaF(0.55)
        qp.setBrush(c)
        qp.drawEllipse(QRectF(win.left() + 20 + i * 16, win.top() + 18, 8, 8))
    qp.setBrush(Qt.NoBrush)
    qp.setPen(QColor(pal.line))
    qp.drawLine(int(win.left()), int(win.top() + 48),
                int(win.right()), int(win.top() + 48))

    body = QFont(); body.setPixelSize(16)
    head = QFont(); head.setPixelSize(16); head.setWeight(QFont.DemiBold)
    y = win.top() + 92
    for txt, role in DOC_LINES:
        if not txt:
            y += 16
            continue
        qp.setFont(head if role == "head" else body)
        qp.setPen(QColor(pal.text if role == "head" else pal.text_dim))
        qp.drawText(QRectF(win.left() + 40, y, win.width() - 80, 26),
                    Qt.AlignLeft | Qt.AlignVCenter, txt)
        y += 28

    # Caret, to show the field is focused.
    qp.fillRect(QRectF(win.left() + 40, y + 4, 2, 18), QColor(pal.accent))

    # The real overlay, with its one shadow.
    ov = overlay_image("listening", "move the review by one week", pal)
    ox = int((W - ov.width()) / 2)
    # Overlap the window's lower edge - that is how it reads on screen: a thing
    # floating above the document, not a caption underneath it.
    oy = int(win.bottom() - CAPSULE_H / 2)
    sh = QColor(0, 0, 0, 70 if pal is theme.DARK else 34)
    for i in range(10, 0, -1):
        c = QColor(sh)
        c.setAlpha(int(sh.alpha() / 10))
        rounded(qp, QRectF(ox - i, oy - i + 3, ov.width() + 2 * i, CAPSULE_H + 2 * i),
                (CAPSULE_H + 2 * i) / 2, c)
    qp.drawImage(ox, oy, ov)

    cap = QFont(); cap.setPixelSize(13)
    qp.setFont(cap)
    qp.setPen(QColor(pal.text_faint))
    qp.drawText(QRectF(0, H - 78, W, 20), Qt.AlignHCenter,
                "Super + H  ·  speak  ·  Super + H")
    qp.end()
    img.save(str(OUT / name))
    print("wrote", name)


# --------------------------------------------------------- overlay states

def overlay_states(pal, name: str):
    rows = [
        ("listening", "the meeting is on Wednesday", "while you speak"),
        ("thinking", "the meeting is on Wednesday at three no at four",
         "applying your corrections"),
        ("done", "The meeting is on Wednesday at four.", "inserted"),
        ("problem", "Microphone muted or gain too low", "something is wrong"),
    ]
    imgs = [(overlay_image(s, t, pal, seed=5 + i), cap)
            for i, (s, t, cap) in enumerate(rows)]
    PAD, GAP = 44, 30
    W = max(i.width() for i, _ in imgs) + 2 * PAD
    W = max(W, 760)
    H = PAD + len(imgs) * (CAPSULE_H + GAP + 20)
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("#0A0A0C" if pal is theme.DARK else "#EFEFEA"))
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing)
    f = QFont(); f.setPixelSize(12)
    y = PAD
    for im, cap in imgs:
        qp.drawImage(PAD, y, im)
        qp.setFont(f)
        qp.setPen(QColor(pal.text_faint))
        qp.drawText(QRectF(PAD, y + CAPSULE_H + 5, 600, 18), Qt.AlignLeft, cap)
        y += CAPSULE_H + GAP + 20
    qp.end()
    img.save(str(OUT / name))
    print("wrote", name)


# ------------------------------------------------------------- wizard

def wizard_shots(pal, prefix: str, app: QApplication):
    w = Wizard(pal)
    w.resize(720, 600)
    names = ["welcome", "hardware", "recommendation", "dependencies",
             "microphone", "shortcut", "download"]
    shots = []
    for i in range(len(STEPS)):
        w.stack.setCurrentIndex(i)
        w.step_label.setText(f"Step {i + 1} of {len(STEPS)}")
        w.back_btn.setVisible(i > 0)
        w.next_btn.setText("Finish" if i == len(STEPS) - 1 else "Continue")
        if names[i] == "download":
            w.stack.currentWidget().on_enter()
        app.processEvents()
        im = w.grab().toImage()
        im.save(str(OUT / f"{prefix}-{names[i]}.png"))
        shots.append(im)
    print("wrote", len(shots), "wizard pages")
    return shots


def wizard_trio(shots, pal, name: str):
    """Three pages side by side for the README banner."""
    pick = [shots[1], shots[2], shots[4]]          # hardware, recommendation, mic
    PAD, GAP = 36, 24
    cw, ch = pick[0].width(), pick[0].height()
    W = PAD * 2 + 3 * cw + 2 * GAP
    H = PAD * 2 + ch
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("#0A0A0C" if pal is theme.DARK else "#EFEFEA"))
    qp = QPainter(img)
    qp.setRenderHint(QPainter.Antialiasing)
    for i, im in enumerate(pick):
        x = PAD + i * (cw + GAP)
        rounded(qp, QRectF(x - 1, PAD - 1, cw + 2, ch + 2), 9,
                QColor(0, 0, 0, 0), QColor(pal.line))
        qp.drawImage(x, PAD, im)
    qp.end()
    img.save(str(OUT / name))
    print("wrote", name)


def main():
    app = QApplication(sys.argv[:1])
    hero(theme.DARK, "hero.png")
    hero(theme.LIGHT, "hero-light.png")
    overlay_states(theme.DARK, "overlay-states.png")
    shots = wizard_shots(theme.DARK, "setup", app)
    wizard_trio(shots, theme.DARK, "setup-trio.png")


if __name__ == "__main__":
    main()
