"""Application entry point."""

from __future__ import annotations

import sys
import traceback

from PyQt6.QtWidgets import QApplication

from workmods.config import APP_NAME, APP_VERSION, WorkmodsConfig
from workmods.ui.main_window import MainWindow
from workmods.ui.theme import APP_STYLESHEET


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main(argv: list[str] | None = None) -> int:
    sys.excepthook = _excepthook
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow(WorkmodsConfig.load())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
