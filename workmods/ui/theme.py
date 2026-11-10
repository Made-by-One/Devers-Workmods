"""Icons and the global stylesheet."""

from __future__ import annotations

from PyQt6.QtGui import QIcon, QPixmap

from workmods.config import DATA_DIR

APP_STYLESHEET = """
    QWidget { background: transparent; color: #c9c5c7; font-family: 'Consolas', monospace; font-size: 13px; }
    QMainWindow { background: #0a0a0b; }
    QTabWidget::pane { border: 1px solid #262326; background: #0e0d0f; }
    QTabBar::tab { background: #0a0a0b; border: 1px solid #262326; border-bottom: none; padding: 10px 20px; margin-right: 2px; color: #858080; }
    QTabBar::tab:selected { background: #0e0d0f; color: #fdfcfc; border-top: 2px solid #a78bfa; }
    QPushButton { background: #0e0d0f; border: 1px solid #3a3438; padding: 8px 16px; color: #c9c5c7; border-radius: 4px; }
    QPushButton:hover { border-color: #858080; color: #fdfcfc; background: #111013; }
    QPushButton:disabled { color: #5c585a; border-color: #262326; }
    QPushButton#primary { background: rgba(167, 139, 250, .07); color: #c9b8ff; border: 1px solid #4a3b7a; }
    QPushButton#primary:hover { background: rgba(167, 139, 250, .13); border-color: #a78bfa; color: #fdfcfc; }
    QPushButton#danger { background: #1a0000; border: 1px solid #5a1a1a; color: #ff8888; }
    QPushButton#danger:hover { background: #5a1a1a; color: #fdfcfc; }
    QLineEdit, QTextEdit, QListWidget, QComboBox { background: #0a0a0b; border: 1px solid #262326; padding: 6px; color: #fdfcfc; border-radius: 4px; outline: none; }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #a78bfa; }
    QComboBox::drop-down { border: none; width: 18px; }
    QComboBox QAbstractItemView { background: #0e0d0f; border: 1px solid #262326; selection-background-color: rgba(167, 139, 250, .12); }
    QListWidget::item { padding: 10px; border-bottom: 1px solid #1b191c; color: #c9c5c7; outline: none; }
    QListWidget::item:hover { background: #111013; }
    QListWidget::item:selected { background: rgba(167, 139, 250, .07); color: #c9b8ff; border-left: 3px solid #a78bfa; outline: none; }
    QScrollBar:vertical { background: #0a0a0b; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: #2a2629; min-height: 20px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QProgressBar { background: #0a0a0b; border: 1px solid #262326; text-align: center; color: #fdfcfc; border-radius: 4px; }
    QProgressBar::chunk { background-color: #a78bfa; }
    QFrame#detailPanel { border: 1px solid #262326; background: #0e0d0f; border-radius: 4px; }
    QLabel#sectionTitle { color: #858080; font-weight: bold; letter-spacing: 1px; }
    QLabel#dim { color: #858080; }
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


__all__ = ["APP_STYLESHEET", "load_icon", "scale_pixmap"]
