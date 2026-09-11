"""Gestaltungssystem.

Bewusst eng gefasst. Die Regeln existieren, damit spaeterer Code nicht anfaengt,
eigene Farben und Radien zu erfinden - genau daran erkennt man Oberflaechen, die
aus vielen unabhaengigen Entscheidungen zusammengesetzt wurden.

  - Eine Akzentfarbe, sonst nur Grauwerte
  - Drei Schriftgrade, zwei Schnitte
  - Radius 6 px, ein einziger Schatten im ganzen Programm
  - Abstaende auf einem 4-px-Raster
  - Zustand ueber Helligkeit und Position, nicht ueber Signalfarben
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str          # Fensterhintergrund
    surface: str     # erhoehte Flaeche (Karten, Eingabefelder)
    surface_alt: str # leicht abgesetzt (Zebrastreifen, Kopfzeilen)
    line: str        # Trennlinien, Rahmen
    text: str        # Fliesstext
    text_dim: str    # Nebensaechliches
    text_faint: str  # Platzhalter, Deaktiviertes
    accent: str      # die eine Akzentfarbe
    accent_dim: str  # ihre ruhige Variante
    warn: str        # ausschliesslich fuer echte Warnungen


DARK = Palette(
    name="dark",
    bg="#131316",
    surface="#1A1A1E",
    surface_alt="#202026",
    line="#2C2C33",
    text="#E8E8E6",
    text_dim="#9A9A96",
    text_faint="#5E5E63",
    accent="#C8944B",      # gedecktes Messing - kein Neonblau, kein Violett
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

# Schriftgrade: nur diese drei.
FONT_SM = 12
FONT_MD = 13
FONT_LG = 20

# Abstaende: Vielfache von 4.
S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 24, 32

RADIUS = 6
RADIUS_PILL = 999


def font_stack() -> str:
    """Systemschrift. Keine mitgelieferte Schrift - die faellt immer auf."""
    return ('"Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", '
            '"Noto Sans", "Cantarell", system-ui, sans-serif')


def mono_stack() -> str:
    return ('"JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", '
            '"DejaVu Sans Mono", monospace')


def stylesheet(p: Palette = DARK) -> str:
    """Das gesamte Aussehen an einer Stelle."""
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

/* --- Flaechen ----------------------------------------------------- */
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

/* --- Schaltflaechen ------------------------------------------------ */
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

/* --- Eingaben ------------------------------------------------------ */
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
    /* kleines Dreieck aus Rahmenlinien - kein Bild noetig */
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

/* --- Schalter (als schlanke Kaestchen, nicht als Spielzeug) -------- */
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

/* --- Fortschritt: eine duenne Linie, kein Balken ------------------- */
QProgressBar {{
    background: {p.line}; border: none; border-radius: 2px;
    max-height: 3px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 2px; }}

/* --- Listen -------------------------------------------------------- */
QListWidget, QTreeWidget, QTableWidget {{
    background: {p.bg}; border: 1px solid {p.line};
    border-radius: {RADIUS}px; outline: none;
}}
QListWidget::item {{ padding: {S2}px {S3}px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {p.surface_alt}; color: {p.text}; }}

/* --- Bildlaufleisten: unauffaellig --------------------------------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.line}; border-radius: 5px;
                               min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {p.line}; border-radius: 5px;
                                 min-width: 28px; }}

/* --- Reiter -------------------------------------------------------- */
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
    """Systemvorgabe hell/dunkel uebernehmen, statt eine zu erzwingen."""
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        hints = QGuiApplication.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        if scheme and scheme() == Qt.ColorScheme.Light:
            return LIGHT
    except Exception:
        pass
    return DARK
