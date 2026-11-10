"""Qt network adapter for the registry.

``registry.py`` stays free of Qt; this module turns an HTTP fetch into a Qt
signal so widgets can consume it without blocking the event loop.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from workmods.registry import Registry


class RegistryStore(QObject):
    """Shared, cached registry used by the catalog and the author studio."""

    loaded = pyqtSignal(object)  # Registry
    failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._registry: Registry | None = None
        self._pending = False

    @property
    def registry(self) -> Registry | None:
        return self._registry

    @property
    def is_loading(self) -> bool:
        return self._pending

    def refresh(self, url: str) -> None:
        if not url:
            self.failed.emit("Registry URL is not configured.")
            return
        if self._pending:
            return
        self._pending = True
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"Workmods-Client")
        request.setTransferTimeout(20000)
        reply = self._nam.get(request)
        reply.finished.connect(lambda: self._on_finished(reply))

    def _on_finished(self, reply: QNetworkReply) -> None:
        self._pending = False
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failed.emit(reply.errorString())
                return
            raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except ValueError as exc:
                self.failed.emit(f"Invalid registry JSON: {exc}")
                return
            try:
                self._registry = Registry.from_payload(payload)
            except ValueError as exc:
                self.failed.emit(str(exc))
                return
            self.loaded.emit(self._registry)
        finally:
            reply.deleteLater()


__all__ = ["RegistryStore"]
