"""Main window: wires the tabs together and owns shared state."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from workmods.config import APP_NAME, APP_VERSION, DATA_DIR, WorkmodsConfig
from workmods.i18n import Localization, resolve_language
from workmods.net import RegistryStore
from workmods.registry import Registry
from workmods.ui.author_tab import AuthorStudioTab
from workmods.ui.catalog_tab import CatalogTab
from workmods.ui.installed_tab import InstalledTab
from workmods.ui.settings_tab import SettingsTab
from workmods.ui.theme import load_icon
from workmods.ui.widgets import OptimizedFluidBackground


class MainWindow(QMainWindow):
    def __init__(self, config: WorkmodsConfig | None = None):
        super().__init__()
        self.config = config or WorkmodsConfig.load()
        self.loc = Localization(resolve_language(self.config.language))
        self.store = RegistryStore(self)

        icon_path = DATA_DIR / "icon" / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setWindowTitle(
            f"{APP_NAME} — {self.loc.t('window_title', 'universal mod manager')}"
        )
        self.resize(1080, 780)

        self.bg = OptimizedFluidBackground(self)
        self.bg.setGeometry(0, 0, 1080, 780)
        self.bg.lower()

        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(16, 16))
        self._create_tabs()
        self._add_tabs()

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 10, 18, 14)
        body_layout.addWidget(self.tabs)
        layout.addWidget(body, 1)

        self._wire_signals()
        self._wire_tab_signals()
        self._refresh_header()
        QTimer.singleShot(100, self.tab_catalog.reload)

    # -- tabs ---------------------------------------------------------------
    def _create_tabs(self) -> None:
        self.tab_catalog = CatalogTab(self.config, self.loc, self.store)
        self.tab_installed = InstalledTab(self.config, self.loc, self.store)
        self.tab_author = AuthorStudioTab(self.config, self.loc, self.store)
        self.tab_settings = SettingsTab(self.config, self.loc)
        self.tab_settings.language_changed.connect(self._on_language_changed)

    def _add_tabs(self) -> None:
        self.tabs.addTab(
            self.tab_catalog, load_icon("library"), self.loc.t("catalog", "CATALOG")
        )
        self.tabs.addTab(
            self.tab_installed, load_icon("folder"), self.loc.t("installed", "INSTALLED")
        )
        self.tabs.addTab(
            self.tab_author, load_icon("edit"), self.loc.t("author", "AUTHOR STUDIO")
        )
        self.tabs.addTab(
            self.tab_settings, load_icon("settings"), self.loc.t("settings", "SETTINGS")
        )

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(76)
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(16)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        wordmark = QLabel("WORKMODS")
        wordmark.setObjectName("wordmark")
        self.tagline = QLabel(self.loc.t("app_tagline", "UNIVERSAL MOD MANAGER"))
        self.tagline.setObjectName("tagline")
        titles.addWidget(wordmark)
        titles.addWidget(self.tagline)
        row.addLayout(titles)
        row.addStretch()

        self.game_chip = QLabel()
        self.game_chip.setObjectName("chip")
        version_chip = QLabel(f"BETA · {APP_VERSION}")
        version_chip.setObjectName("chipAccent")
        row.addWidget(self.game_chip)
        row.addWidget(version_chip)
        return header

    def _refresh_header(self) -> None:
        game = self.config.game(self.config.active_game_id)
        name = game.name if game else self.config.active_game_id
        self.game_chip.setText(f"{self.loc.t('profile', 'PROFILE')} · {name.upper()}")
        self.tagline.setText(self.loc.t("app_tagline", "UNIVERSAL MOD MANAGER"))

    def _wire_signals(self) -> None:
        self.store.loaded.connect(self._on_registry_loaded)

    def _wire_tab_signals(self) -> None:
        self.tab_catalog.install_finished.connect(self._on_mods_on_disk_changed)
        self.tab_installed.mods_changed.connect(self._on_mods_on_disk_changed)
        self.tab_author.mods_changed.connect(self._on_mods_on_disk_changed)
        self.tab_settings.configuration_changed.connect(self._on_configuration_changed)

    def _on_language_changed(self, language: str) -> None:
        """Apply a new language without restarting: rebuild the tabs in place."""
        self.loc = Localization(language)
        self.config.language = language
        QTimer.singleShot(0, self._rebuild_tabs)

    def _rebuild_tabs(self) -> None:
        index = self.tabs.currentIndex()
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        self._create_tabs()
        self._add_tabs()
        self._wire_tab_signals()
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))
        self.setWindowTitle(
            f"{APP_NAME} — {self.loc.t('window_title', 'universal mod manager')}"
        )
        self._refresh_header()
        self.tab_catalog.refresh_games()
        self.tab_installed.scan()
        self.tab_author.refresh_data()

    def _on_registry_loaded(self, registry: Registry) -> None:
        # New game ids may have appeared in the registry: refresh both filters.
        self.tab_installed.refresh_games()
        self.tab_catalog.refresh_games()

    def _on_mods_on_disk_changed(self, _mod_id: str = "") -> None:
        self.tab_installed.scan()
        self.tab_author.refresh_data()
        self.tab_catalog.refresh_games()

    def _on_configuration_changed(self) -> None:
        self._refresh_header()
        self.tab_catalog.refresh_games()
        self.tab_installed.refresh_games()
        self.tab_author.refresh_data()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        self.bg.resize(self.size())
        super().resizeEvent(event)


__all__ = ["MainWindow"]
