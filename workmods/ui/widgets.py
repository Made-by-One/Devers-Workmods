"""Reusable decorative and background widgets."""

from __future__ import annotations

import math
import time

import requests
from PyQt6.QtCore import QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QWidget


class OptimizedFluidBackground(QWidget):
    """The animated grid backdrop. Purely decorative."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.cell_size = 16
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.cols = 0
        self.rows = 0
        self.current: list[list[float]] = []
        self.previous: list[list[float]] = []

    def init_grid(self) -> None:
        if self.width() > 0 and self.height() > 0:
            self.cols = self.width() // self.cell_size
            self.rows = self.height() // self.cell_size
            self.current = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]
            self.previous = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        self.init_grid()
        super().resizeEvent(event)

    def tick(self) -> None:
        if not self.current:
            return
        for y in range(self.rows):
            for x in range(self.cols):
                dist = math.hypot(x - self.cols / 2, y - self.rows / 2)
                self.current[y][x] = math.sin(dist * 0.1 - time.time() * 1.5) * math.exp(-dist * 0.03)
        self.previous, self.current = self.current, self.previous
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        if not self.previous:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        for y in range(self.rows):
            for x in range(self.cols):
                brightness = int(((self.previous[y][x] + 1) / 2) * 25)
                if brightness > 5:
                    painter.fillRect(
                        QRectF(x * self.cell_size, y * self.cell_size, self.cell_size - 1, self.cell_size - 1),
                        QColor(brightness, brightness, brightness),
                    )


class AsciiLogo(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            "color: #FFFFFF; background: transparent; font-family: 'Consolas', monospace; "
            "font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        )
        self.setText(
            """
 ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗███╗   ███╗ ██████╗ ██████╗ ███████╗
 ██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝████╗ ████║██╔═══██╗██╔══██╗██╔════╝
 ██║ █╗ ██║██║   ██║██████╔╝█████╔╝ ██╔████╔██║██║   ██║██║  ██║███████╗
 ██║███╗██║██║   ██║██╔══██╗██╔═██╗ ██║╚██╔╝██║██║   ██║██║  ██║╚════██║
 ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗██║ ╚═╝ ██║╚██████╔╝██████╔╝███████║
  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
        """
        )


class UploadDialog(QDialog):
    """Generic modal progress dialog used for install and publish."""

    def __init__(self, parent: QWidget | None = None, title: str = "Processing"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Preparing...")
        self.status_label.setStyleSheet("color: #c9c5c7; font-weight: bold;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addStretch()

    def set_status(self, text: str, value: int | None = None) -> None:
        self.status_label.setText(text)
        if value is not None:
            self.progress.setValue(max(0, min(100, int(value))))


class ImageDownloader(QThread):
    """Fetch a registry image off the UI thread."""

    loaded = pyqtSignal(str, bytes)

    def __init__(self, url: str, tag: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.tag = tag

    def run(self) -> None:
        try:
            response = requests.get(self.url, timeout=15)
            if response.status_code == 200:
                self.loaded.emit(self.tag, response.content)
        except requests.RequestException:
            pass


__all__ = ["AsciiLogo", "ImageDownloader", "OptimizedFluidBackground", "UploadDialog"]
