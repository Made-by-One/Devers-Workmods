"""Main window: wires the tabs together and owns shared state."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from workmods.config import APP_NAME, DATA_DIR, WorkmodsConfig
from workmods.i18n import Localization
from workmods.net import RegistryStore
from workmods.registry import Registry
from workmods.ui.author_tab import AuthorStudioTab
from workmods.ui.catalog_tab import CatalogTab
from workmods.ui.installed_tab import InstalledTab
from workmods.ui.settings_tab import SettingsTab
from workmods.ui.theme import load_icon
from workmods.ui.widgets import AsciiLogo, OptimizedFluidBackground


class MainWindow(QMainWindow):
    def __init__(self, config: WorkmodsConfig | None = None):
        super().__init__()
        self.config = config or WorkmodsConfig.load()
        self.loc = Localization(self.config.language)
        self.store = RegistryStore(self)

        icon_path = DATA_DIR / "icon" / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setWindowTitle(f"{APP_NAME} — universal mod manager")
        self.resize(1080, 780)

        self.bg = OptimizedFluidBackground(self)
        self.bg.setGeometry(0, 0, 1080, 780)
        self.bg.lower()

        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QHBoxLayout()
        header.addWidget(AsciiLogo())
        header.addStretch()
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tab_catalog = CatalogTab(self.config, self.loc, self.store)
        self.tab_installed = InstalledTab(self.config, self.loc, self.store)
        self.tab_author = AuthorStudioTab(self.config, self.loc, self.store)
        self.tab_settings = SettingsTab(self.config, self.loc)

        self.tabs.addTab(self.tab_catalog, load_icon("library"), self.loc.t("catalog", "CATALOG"))
        self.tabs.addTab(self.tab_installed, load_icon("folder"), self.loc.t("installed", "INSTALLED"))
        self.tabs.addTab(self.tab_author, load_icon("edit"), self.loc.t("author", "AUTHOR STUDIO"))
        self.tabs.addTab(self.tab_settings, load_icon("settings"), self.loc.t("settings", "SETTINGS"))
        layout.addWidget(self.tabs)

        self._wire_signals()
        QTimer.singleShot(100, self.tab_catalog.reload)

    def _wire_signals(self) -> None:
        self.tab_catalog.install_finished.connect(self._on_mods_on_disk_changed)
        self.tab_installed.mods_changed.connect(self._on_mods_on_disk_changed)
        self.tab_author.mods_changed.connect(self._on_mods_on_disk_changed)
        self.tab_settings.configuration_changed.connect(self._on_configuration_changed)
        self.store.loaded.connect(self._on_registry_loaded)

    def _on_registry_loaded(self, registry: Registry) -> None:
        # New game ids may have appeared in the registry: refresh both filters.
        self.tab_installed.refresh_games()
        self.tab_catalog.refresh_games()

    def _on_mods_on_disk_changed(self, _mod_id: str = "") -> None:
        self.tab_installed.scan()
        self.tab_author.refresh_data()
        self.tab_catalog.refresh_games()

    def _on_configuration_changed(self) -> None:
        self.tab_catalog.refresh_games()
        self.tab_installed.refresh_games()
        self.tab_author.refresh_data()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        self.bg.resize(self.size())
        super().resizeEvent(event)


__all__ = ["MainWindow"]
