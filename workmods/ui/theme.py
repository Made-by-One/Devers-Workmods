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
        color: #e6e6f0;
        font-family: {FONT_SANS};
        font-size: 13px;
    }}
    QMainWindow {{ background: #09090f; }}
    QDialog {{ background: #0d0d15; }}

    QWidget#header {{ background: #0b0b12; border-bottom: 1px solid #1c1c28; }}
    QLabel#wordmark {{ color: #f7f5ff; font-size: 21px; font-weight: 800; letter-spacing: 7px; }}
    QLabel#tagline {{ color: #6d6d85; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
    QLabel#chip {{
        background: #14141e; border: 1px solid #262636; border-radius: 9px;
        padding: 4px 10px; color: #b9b9cf; font-size: 11px;
    }}
    QLabel#chipAccent {{
        background: {ACCENT_SOFT}; border: 1px solid rgba(139, 92, 246, 0.45);
        border-radius: 9px; padding: 4px 10px; color: #c9b8ff;
        font-size: 11px; font-weight: 700; letter-spacing: 1px;
    }}

    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: transparent; border: none; border-radius: 8px;
        padding: 9px 18px; margin-right: 4px;
        color: #8b8ba3; font-size: 11px; font-weight: 600; letter-spacing: 1px;
    }}
    QTabBar::tab:hover {{ color: #d6d3e6; background: #15151f; }}
    QTabBar::tab:selected {{ color: #f1edff; background: #1b1729; }}

    QPushButton {{
        background: #15151f; border: 1px solid #2a2a3a; border-radius: 8px;
        padding: 8px 14px; color: #dcdce9;
        font-weight: 600; font-size: 12px;
    }}
    QPushButton:hover {{ background: #1c1c29; border-color: #3b3b52; color: #ffffff; }}
    QPushButton:pressed {{ background: #12121b; }}
    QPushButton:disabled {{ background: #101018; border-color: #20202c; color: #565669; }}
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
        background: #0c0c14; border: 1px solid #252536; border-radius: 8px;
        padding: 8px 12px; color: #f2f0fa;
        selection-background-color: #7c3aed; selection-color: #ffffff;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QComboBox:on {{
        border-color: #8b5cf6; background: #0e0e18;
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
        background: #0d0d15; border: 1px solid #1d1d29;
        border-radius: 12px; outline: none;
    }}
    QListWidget::item {{
        background: transparent; border: none; border-radius: 8px;
        padding: 12px 10px; margin: 1px 2px; color: #cfcfdd;
    }}
    QListWidget::item:hover {{ background: #14141e; }}
    QListWidget::item:selected {{ background: #1a1526; color: #ece5ff; }}

    QLabel#panelTitle {{ color: #f7f5ff; font-size: 21px; font-weight: 700; }}
    QLabel#rowTitle {{ color: #f1eff9; font-size: 13px; font-weight: 600; }}
    QLabel#sectionTitle {{ color: #7e7e99; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
    QLabel#meta {{ color: #8d8da6; font-size: 12px; }}
    QLabel#dim {{ color: #8d8da6; }}
    QLabel#emptyState {{ color: #6f6f88; font-size: 13px; }}
    QTextEdit#description {{
        background: transparent; border: none; padding: 0; color: #b7b7cb;
    }}

    QFrame#card {{ background: #101018; border: 1px solid #22222f; border-radius: 12px; }}
    QFrame#detailPanel {{ background: #0e0e16; border: 1px solid #22222f; border-radius: 12px; }}

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
