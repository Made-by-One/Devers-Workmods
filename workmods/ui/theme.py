"""Icons and the global stylesheet."""

from __future__ import annotations

from PyQt6.QtGui import QIcon, QPixmap

from workmods.config import DATA_DIR

FONT_SANS = '"Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"'
FONT_MONO = '"Consolas", "JetBrains Mono", "DejaVu Sans Mono"'

ACCENT = "#8b5cf6"
ACCENT_SOFT = "rgba(139, 92, 246, 0.12)"

APP_STYLESHEET = f"""
    QWidget {{
        background: transparent;
        color: #e9e7f3;
        font-family: {FONT_SANS};
        font-size: 13px;
    }}
    QMainWindow {{ background: #08080d; }}
    QDialog {{ background: #0c0c14; }}
    QDialog QLabel {{ color: #b6b4c8; }}

    QWidget#header {{
        background: #0a0a11;
        border-bottom: 1px solid #1e1e2c;
    }}
    QLabel#wordmark {{ color: #f8f6ff; font-size: 20px; font-weight: 800; letter-spacing: 6px; }}
    QLabel#tagline {{ color: #68687f; font-size: 9px; font-weight: 600; letter-spacing: 2px; }}
    QLabel#chip {{
        background: #12121b; border: 1px solid #252534; border-radius: 9px;
        padding: 5px 11px; color: #b3b1c6; font-size: 10px; font-weight: 600;
        letter-spacing: 1px;
    }}
    QLabel#chipAccent {{
        background: {ACCENT_SOFT}; border: 1px solid rgba(139, 92, 246, 0.42);
        border-radius: 9px; padding: 5px 11px; color: #cdbcff;
        font-size: 10px; font-weight: 700; letter-spacing: 1px;
    }}

    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: transparent; border: 1px solid transparent; border-radius: 9px;
        padding: 9px 17px; margin-right: 5px;
        color: #86849b; font-size: 10px; font-weight: 700; letter-spacing: 1.4px;
    }}
    QTabBar::tab:hover {{ color: #dcd8ea; background: #14141d; }}
    QTabBar::tab:selected {{
        color: #f4efff; background: #1a1428;
        border: 1px solid #34274f;
    }}

    QPushButton {{
        background: #14141d; border: 1px solid #292938; border-radius: 9px;
        padding: 8px 15px; color: #dddbea;
        font-weight: 600; font-size: 11px; letter-spacing: 0.2px;
    }}
    QPushButton:hover {{ background: #1b1b27; border-color: #3d3d53; color: #ffffff; }}
    QPushButton:pressed {{ background: #101018; }}
    QPushButton:disabled {{ background: #0f0f16; border-color: #1e1e29; color: #555369; }}
    QPushButton#primary {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #a855f7);
        border: 1px solid #8b5cf6; color: #ffffff; font-weight: 700;
    }}
    QPushButton#primary:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #c084fc);
        border-color: #a78bfa;
    }}
    QPushButton#danger {{
        background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.35);
        color: #fca5a5;
    }}
    QPushButton#danger:hover {{ background: rgba(239, 68, 68, 0.18); border-color: #ef4444; color: #fee2e2; }}
    QPushButton#primary:disabled {{
        background: #1a1723; border-color: #2c2740; color: #6b6480;
    }}
    QPushButton#danger:disabled {{
        background: #121018; border-color: #2a2028; color: #7a6262;
    }}

    QLineEdit, QTextEdit, QComboBox {{
        background: #0b0b13; border: 1px solid #282838; border-radius: 9px;
        padding: 9px 12px; color: #f3f1fb;
        selection-background-color: #7c3aed; selection-color: #ffffff;
    }}
    QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{ border-color: #35354a; }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QComboBox:on {{
        border-color: #8b5cf6; background: #0d0d17;
    }}
    QLineEdit:disabled {{ color: #565669; border-color: #20202c; }}
    QComboBox {{ padding-right: 24px; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{
        image: url('{DATA_DIR.as_posix()}/icon/chevron.png');
        width: 10px; height: 6px;
    }}
    QComboBox QAbstractItemView {{
        background: #12121c; border: 1px solid #2a2a3a; border-radius: 8px;
        padding: 4px; outline: none;
        selection-background-color: rgba(139, 92, 246, 0.25); selection-color: #ffffff;
    }}

    QListWidget {{
        background: #0c0c14; border: 1px solid #20202e;
        border-radius: 12px; outline: none; padding: 5px;
    }}
    QListWidget::item {{
        background: transparent; border: 1px solid transparent; border-radius: 9px;
        padding: 0; margin: 2px 1px; color: #cfcddd;
    }}
    QListWidget::item:hover {{ background: #13131d; border-color: #242434; }}
    QListWidget::item:selected {{ background: #1b152b; border-color: #352850; color: #f1ecff; }}

    QLabel#panelTitle {{ color: #f8f6ff; font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }}
    QLabel#rowTitle {{ color: #f1eff9; font-size: 13px; font-weight: 600; }}
    QLabel#sectionTitle {{ color: #828096; font-size: 9px; font-weight: 700; letter-spacing: 1.8px; }}
    QLabel#meta {{ color: #8c8aa1; font-size: 12px; }}
    QLabel#dim {{ color: #7e7c92; font-size: 11px; }}
    QLabel#fieldLabel {{ color: #9a98ad; font-size: 12px; font-weight: 500; }}
    QLabel#emptyState {{ color: #716f87; font-size: 13px; }}
    QLabel#countChip {{
        background: #101018; border: 1px solid #242432; border-radius: 8px;
        padding: 5px 10px; color: #8f8da5; font-size: 10px;
        font-weight: 700; letter-spacing: 1px;
    }}
    QLabel#statValue {{ color: #f6f3ff; font-size: 22px; font-weight: 700; }}
    QLabel#statLabel {{ color: #7f7d93; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; }}
    QLabel#infoValue {{ color: #e7e3f3; font-size: 12px; font-weight: 600; }}
    QLabel#accountHint {{ color: #85839a; font-size: 12px; }}
    QLabel#bodyText {{ color: #b9b7ca; font-size: 12px; }}
    QTextEdit#description {{
        background: transparent; border: none; padding: 0; color: #b9b7ca;
    }}

    QFrame#card {{ background: #0f0f18; border: 1px solid #232331; border-radius: 13px; }}
    QFrame#detailPanel {{ background: #0d0d16; border: 1px solid #232331; border-radius: 13px; }}
    QFrame#statCard {{ background: #0c0c14; border: 1px solid #21212f; border-radius: 11px; }}
    QFrame#divider {{ background: #1f1f2d; border: none; }}
    QScrollArea {{ background: transparent; border: none; }}
    QFrame#accountCard {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #12101c, stop:1 #0f0f18);
        border: 1px solid #2b2440; border-radius: 13px;
    }}

    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #2b2b3c; min-height: 24px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: #3c3c52; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #2b2b3c; min-width: 24px; border-radius: 4px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:hover {{ background: #22222f; }}

    QProgressBar {{
        background: #0c0c14; border: 1px solid #252536; border-radius: 6px;
        text-align: center; color: #f2f0fa; min-height: 10px;
    }}
    QProgressBar::chunk {{ background-color: #8b5cf6; border-radius: 5px; }}

    QToolTip {{
        background: #1b1b26; color: #e6e6f0; border: 1px solid #3b3b52;
        padding: 6px 8px;
    }}
"""


def load_icon(name: str) -> QIcon:
    """Load a monochrome PNG icon and derive a selected (hover) variant."""
    path = DATA_DIR / "icon" / f"{name}.png"
    if not path.exists():
        return QIcon()
    pixmap = QPixmap(str(path))
    image = pixmap.toImage()
    image.invertPixels()
    icon = QIcon()
    icon.addPixmap(pixmap, QIcon.Mode.Normal)
    icon.addPixmap(QPixmap.fromImage(image), QIcon.Mode.Selected)
    icon.addPixmap(pixmap, QIcon.Mode.Active)
    return icon


def scale_pixmap(data: bytes, width: int, height: int) -> QPixmap:
    from PyQt6.QtCore import Qt

    pixmap = QPixmap()
    pixmap.loadFromData(data)
    return pixmap.scaled(
        width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )


__all__ = ["ACCENT", "APP_STYLESHEET", "FONT_MONO", "load_icon", "scale_pixmap"]
