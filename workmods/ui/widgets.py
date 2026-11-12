"""Reusable decorative and background widgets."""

from __future__ import annotations

import math
import time

import requests
from PyQt6.QtCore import QBuffer, QIODevice, QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QMovie
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class OptimizedFluidBackground(QWidget):
    """The animated grid backdrop. Purely decorative."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.cell_size = 18
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
                brightness = int(((self.previous[y][x] + 1) / 2) * 12)
                if brightness > 5:
                    painter.fillRect(
                        QRectF(x * self.cell_size, y * self.cell_size, self.cell_size - 1, self.cell_size - 1),
                        QColor(brightness, brightness, brightness),
                    )


class CoverLabel(QLabel):
    """Image label that paints rounded, cropped covers with a built-in placeholder."""

    def __init__(
        self,
        radius: int = 12,
        placeholder: str = "NO COVER",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.radius = radius
        self.placeholder = placeholder
        self._cover = QPixmap()
        self._movie: QMovie | None = None
        self._movie_buffer: QBuffer | None = None

    def set_cover(self, pixmap: QPixmap) -> None:
        self._stop_movie()
        self._cover = pixmap
        self.update()

    def set_movie(self, data: bytes) -> None:
        self._stop_movie()
        buffer = QBuffer()
        buffer.setData(data)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        movie = QMovie()
        movie.setDevice(buffer)
        movie.frameChanged.connect(self._on_movie_frame)
        self._movie = movie
        self._movie_buffer = buffer
        movie.start()
        frame = movie.currentPixmap()
        if not frame.isNull():
            self._cover = frame
        self.update()

    def _on_movie_frame(self) -> None:
        if self._movie is not None:
            frame = self._movie.currentPixmap()
            if not frame.isNull():
                self._cover = frame
            self.update()

    def _stop_movie(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            self._movie.deleteLater()
        self._movie = None
        self._movie_buffer = None

    def clear_cover(self, placeholder: str | None = None) -> None:
        self._stop_movie()
        self._cover = QPixmap()
        if placeholder is not None:
            self.placeholder = placeholder
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.setClipPath(path)

        if self._cover.isNull():
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor("#16121f"))
            gradient.setColorAt(1.0, QColor("#0c0c14"))
            painter.fillRect(rect, gradient)
            painter.setPen(QColor("#5d5d75"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholder)
        else:
            scaled = self._cover.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            offset_x = (scaled.width() - self.width()) // 2
            offset_y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(-offset_x, -offset_y, scaled)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#262636"), 1))
        painter.drawRoundedRect(rect, self.radius, self.radius)
        painter.end()


class ElidedLabel(QLabel):
    """Single-line label that clips long text with an ellipsis instead of stretching."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        self._full = text
        super().setText(text)
        self.update()

    def full_text(self) -> str:
        return self._full

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        elided = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, self.width()
        )
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), int(self.alignment()), elided)
        painter.end()


def initial_pixmap(text: str, size: int = 38) -> QPixmap:
    """Deterministic gradient tile with initials, used where no icon is available."""
    palettes = [
        ("#4c1d95", "#8b5cf6"),
        ("#0f766e", "#2dd4bf"),
        ("#9d174d", "#f472b6"),
        ("#9a3412", "#fb923c"),
        ("#1e3a8a", "#60a5fa"),
        ("#3f6212", "#a3e635"),
    ]
    start, end = palettes[sum(map(ord, text)) % len(palettes)]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor(start))
    gradient.setColorAt(1.0, QColor(end))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.28, size * 0.28)
    initials = "".join(word[0] for word in text.replace("-", " ").split()[:2]).upper() or "?"
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", max(7, int(size * 0.34)), QFont.Weight.Bold))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pixmap


class ModRow(QWidget):
    """One catalog row: avatar, name, metadata and an installed badge."""

    def __init__(self, name: str, meta: str, badge: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        avatar = QLabel()
        avatar.setPixmap(initial_pixmap(name, 38))
        avatar.setFixedSize(38, 38)
        avatar.setStyleSheet("background: transparent;")
        layout.addWidget(avatar)

        text = QVBoxLayout()
        text.setSpacing(3)
        title = ElidedLabel(name)
        title.setObjectName("rowTitle")
        subtitle = ElidedLabel(meta)
        subtitle.setObjectName("meta")
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)

        if badge:
            label = QLabel(badge.upper())
            label.setObjectName("chipAccent")
            layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Clicks must reach the list view underneath so selection keeps working.
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class UploadDialog(QDialog):
    """Generic modal progress dialog used for install and publish."""

    def __init__(self, parent: QWidget | None = None, title: str = "Processing"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        self.status_label = QLabel("Preparing...")
        self.status_label.setObjectName("rowTitle")
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


__all__ = [
    "CoverLabel",
    "ElidedLabel",
    "ImageDownloader",
    "ModRow",
    "OptimizedFluidBackground",
    "UploadDialog",
    "initial_pixmap",
]
