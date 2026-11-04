"""Design system.

Deliberately narrow. These rules exist so later code does not start inventing
its own colours and radii - that is exactly what makes an interface look like a
pile of independent decisions rather than one design.

  - One accent colour, greys for everything else
  - Three type sizes, two weights
  - 6 px radius, a single shadow in the entire program
  - Spacing on a 4 px grid
  - State conveyed through brightness and position, not signal colours
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str          # window background
    surface: str     # raised surface (cards, inputs)
    surface_alt: str # slightly offset (row stripes, headers)
    line: str        # dividers, borders
    text: str        # body text
    text_dim: str    # secondary
    text_faint: str  # placeholders, disabled
    accent: str      # the one accent colour
    accent_dim: str  # its quiet variant
    warn: str        # real warnings only


DARK = Palette(
    name="dark",
    bg="#131316",
    surface="#1A1A1E",
    surface_alt="#202026",
    line="#2C2C33",
    text="#E8E8E6",
    text_dim="#9A9A96",
    text_faint="#5E5E63",
    accent="#C8944B",      # muted brass - no neon blue, no violet
    accent_dim="#7A5B2E",
    warn="#C4674B",
)

LIGHT = Palette(
    name="light",
    bg="#FAFAF8",
    surface="#FFFFFF",
    surface_alt="#F2F2EF",
    line="#E2E2DD",
    text="#1B1B19",
    text_dim="#6B6B66",
    text_faint="#A0A09A",
    accent="#8A5F22",
    accent_dim="#C9B591",
    warn="#A8442A",
)

# Type sizes: only these three.
FONT_SM = 12
FONT_MD = 13
FONT_LG = 20

# Spacing: multiples of 4.
S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 24, 32

RADIUS = 6
RADIUS_PILL = 999


def font_stack() -> str:
    """System font. Never a bundled typeface - those always look out of place."""
    return ('"Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", '
            '"Noto Sans", "Cantarell", system-ui, sans-serif')


def mono_stack() -> str:
    return ('"JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", '
            '"DejaVu Sans Mono", monospace')


def stylesheet(p: Palette = DARK) -> str:
    """The entire look, in one place."""
    return f"""
* {{
    font-family: {font_stack()};
    font-size: {FONT_MD}px;
    color: {p.text};
}}
QWidget#root, QDialog, QMainWindow {{ background: {p.bg}; }}

/* --- Text --------------------------------------------------------- */
QLabel[role="title"]   {{ font-size: {FONT_LG}px; font-weight: 600;
                          color: {p.text}; }}
QLabel[role="lead"]    {{ font-size: {FONT_MD}px; color: {p.text_dim}; }}
QLabel[role="caption"] {{ font-size: {FONT_SM}px; color: {p.text_faint}; }}
QLabel[role="section"] {{ font-size: {FONT_SM}px; color: {p.text_dim};
                          font-weight: 600; }}
QLabel[role="warn"]    {{ font-size: {FONT_SM}px; color: {p.warn}; }}
QLabel[role="mono"]    {{ font-family: {mono_stack()}; font-size: {FONT_SM}px;
                          color: {p.text_dim}; }}

/* --- Surfaces ----------------------------------------------------- */
QFrame[role="card"] {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS}px;
}}
QFrame[role="card"][selected="true"] {{
    border: 1px solid {p.accent};
    background: {p.surface_alt};
}}
QFrame[role="rule"] {{ background: {p.line}; border: none; max-height: 1px; }}

/* --- Buttons ------------------------------------------------------- */
QPushButton {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS}px;
    padding: 7px 14px;
    color: {p.text};
}}
QPushButton:hover  {{ background: {p.surface_alt}; border-color: {p.text_faint}; }}
QPushButton:pressed {{ background: {p.bg}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.line};
                        background: {p.bg}; }}
QPushButton[role="primary"] {{
    background: {p.accent}; border-color: {p.accent}; color: #17130C;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{ background: {p.text}; border-color: {p.text};
                                     color: {p.bg}; }}
QPushButton[role="primary"]:disabled {{ background: {p.accent_dim};
                                        border-color: {p.accent_dim};
                                        color: {p.text_faint}; }}
QPushButton[role="quiet"] {{ background: transparent; border-color: transparent;
                             color: {p.text_dim}; }}
QPushButton[role="quiet"]:hover {{ color: {p.text};
                                   background: {p.surface_alt}; }}

/* --- Inputs -------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background: {p.bg};
    border: 1px solid {p.line};
    border-radius: {RADIUS}px;
    padding: 6px 10px;
    selection-background-color: {p.accent};
    selection-color: #17130C;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border-color: {p.accent};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    /* a small triangle made from borders - no image asset needed */
    width: 0; height: 0; margin-right: 10px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p.text_dim};
}}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.line};
    selection-background-color: {p.surface_alt};
    outline: none; padding: 4px;
}}

/* --- Checkboxes and radios: plain boxes, not toys ------------------ */
QCheckBox, QRadioButton {{ spacing: {S2}px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {p.text_faint};
    background: {p.bg};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.accent}; border-color: {p.accent};
}}

/* --- Progress: a thin line, not a chunky bar ----------------------- */
QProgressBar {{
    background: {p.line}; border: none; border-radius: 2px;
    max-height: 3px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 2px; }}

/* --- Lists --------------------------------------------------------- */
QListWidget, QTreeWidget, QTableWidget {{
    background: {p.bg}; border: 1px solid {p.line};
    border-radius: {RADIUS}px; outline: none;
}}
QListWidget::item {{ padding: {S2}px {S3}px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {p.surface_alt}; color: {p.text}; }}

/* --- Scrollbars: unobtrusive --------------------------------------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.line}; border-radius: 5px;
                               min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {p.line}; border-radius: 5px;
                                 min-width: 28px; }}

/* --- Tabs ---------------------------------------------------------- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; border: none; padding: {S2}px {S3}px;
    color: {p.text_dim}; margin-right: {S1}px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {p.text}; border-bottom-color: {p.accent}; }}
QTabBar::tab:hover {{ color: {p.text}; }}

QToolTip {{
    background: {p.surface}; color: {p.text};
    border: 1px solid {p.line}; padding: {S1}px {S2}px; border-radius: 4px;
}}
"""


def detect_palette() -> Palette:
    """Follow the system light/dark preference instead of forcing one."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        hints = QGuiApplication.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        if scheme and scheme() == Qt.ColorScheme.Light:
            return LIGHT
    except Exception:
        pass
    return DARK
