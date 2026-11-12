"""Catalog tab: browse the registry and install mods for a chosen game."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from workmods.config import WorkmodsConfig
from workmods.i18n import Localization
from workmods.models import Mod
from workmods.net import RegistryStore
from workmods.registry import ALL_GAMES, Registry
from workmods.storage import is_mod_installed
from workmods.ui.common import populate_game_filter, selected_game_id
from workmods.ui.theme import load_icon, scale_pixmap
from workmods.ui.widgets import CoverLabel, ImageDownloader, ModRow, UploadDialog
from workmods.ui.workers import InstallWorker
from workmods.utils import open_folder


class CatalogTab(QWidget):
    install_started = pyqtSignal(str)
    install_finished = pyqtSignal(str)

    def __init__(
        self,
        config: WorkmodsConfig,
        loc: Localization,
        store: RegistryStore,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.config = config
        self.loc = loc
        self.store = store
        self._worker: InstallWorker | None = None
        self._image_workers: list[ImageDownloader] = []
        self._build_ui()

        self.store.loaded.connect(self._on_registry_loaded)
        self.store.failed.connect(self._on_registry_failed)

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.loc.t("search", "SEARCH MODS..."))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(load_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._refresh_list)

        self.count_label = QLabel()
        self.count_label.setObjectName("countChip")

        self.game_filter = QComboBox()
        self.game_filter.setMinimumWidth(190)
        self.game_filter.setToolTip(self.loc.t("filter_game", "Show mods for one game"))
        self.game_filter.currentIndexChanged.connect(self._refresh_list)

        self.btn_refresh = QPushButton(load_icon("refresh"), "")
        self.btn_refresh.setFixedWidth(40)
        self.btn_refresh.setToolTip(self.loc.t("refresh", "Refresh catalog"))
        self.btn_refresh.clicked.connect(self.reload)

        top_layout.addWidget(self.search, 1)
        top_layout.addWidget(self.count_label)
        top_layout.addWidget(self.game_filter)
        top_layout.addWidget(self.btn_refresh)
        layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list = QListWidget()
        self.list.setSpacing(0)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.currentItemChanged.connect(self._on_select)
        splitter.addWidget(self.list)

        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(16)

        self.banner_label = CoverLabel(radius=12, placeholder=self.loc.t("no_cover", "NO COVER"))
        self.banner_label.setFixedHeight(168)

        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)
        self.icon_label = CoverLabel(radius=14, placeholder="")
        self.icon_label.setFixedSize(72, 72)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        self.title_label = QLabel(self.loc.t("select_mod", "SELECT A MOD"))
        self.title_label.setObjectName("panelTitle")
        self.author_label = QLabel("")
        self.author_label.setObjectName("meta")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.author_label)
        title_layout.addStretch()

        info_layout.addWidget(self.icon_label)
        info_layout.addLayout(title_layout, 1)

        self.tags_row = QHBoxLayout()
        self.tags_row.setSpacing(8)

        self.desc_label = QTextEdit()
        self.desc_label.setObjectName("description")
        self.desc_label.setReadOnly(True)

        self.info_frame = QFrame()
        self.info_frame.setObjectName("statCard")
        info_grid = QHBoxLayout(self.info_frame)
        info_grid.setContentsMargins(16, 12, 16, 12)
        info_grid.setSpacing(20)
        self.info_game = self._info_cell(
            info_grid, self.loc.t("game", "GAME").rstrip(":")
        )
        self.info_version = self._info_cell(
            info_grid, self.loc.t("version", "Version:").rstrip(":")
        )
        self.info_author = self._info_cell(
            info_grid, self.loc.t("author_label", "Author:").rstrip(":")
        )
        self.info_entry = self._info_cell(
            info_grid, self.loc.t("entry_asset", "Entry Asset:").rstrip(":")
        )

        self.btn_install = QPushButton(self.loc.t("install", "INSTALL"))
        self.btn_install.setObjectName("primary")
        self.btn_install.setMinimumHeight(42)
        self.btn_install.setMinimumWidth(200)
        self.btn_install.setEnabled(False)
        self.btn_install.clicked.connect(self._install)

        self.btn_folder = QPushButton(load_icon("folder"), self.loc.t("open_folder", "OPEN FOLDER"))
        self.btn_folder.setMinimumHeight(42)
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setEnabled(False)
        self.btn_folder.hide()

        detail_layout.addWidget(self.banner_label)
        detail_layout.addLayout(info_layout)
        detail_layout.addLayout(self.tags_row)
        detail_layout.addWidget(self.desc_label, 1)
        detail_layout.addWidget(self.info_frame)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addWidget(self.btn_install)
        btn_box.addWidget(self.btn_folder)
        btn_box.addStretch()
        detail_layout.addLayout(btn_box)

        splitter.addWidget(self.detail_frame)
        splitter.setSizes([360, 620])
        splitter.setHandleWidth(14)
        layout.addWidget(splitter, 1)

        populate_game_filter(self.game_filter, self.config, None, self.loc.t("all_games", "ALL GAMES"))
        self.count_label.setText(f"0 {self.loc.t('found', 'FOUND')}")
        self._show_empty()

    # -- registry -----------------------------------------------------------
    def reload(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.store.refresh(self.config.registry_url)

    def _on_registry_loaded(self, registry: Registry) -> None:
        self.btn_refresh.setEnabled(True)
        populate_game_filter(
            self.game_filter, self.config, registry, self.loc.t("all_games", "ALL GAMES")
        )
        self._refresh_list()

    def _on_registry_failed(self, message: str) -> None:
        self.btn_refresh.setEnabled(True)
        if self.store.registry is not None:
            # Keep showing the last good registry instead of an empty catalog.
            self._refresh_list()
            return
        self.list.clear()
        self.count_label.setText(f"0 {self.loc.t('found', 'FOUND')}")
        self._show_empty()
        self.desc_label.setPlainText(
            f"{self.loc.t('registry_error', 'Could not load the registry')}:\n{message}"
        )

    def refresh_games(self) -> None:
        populate_game_filter(
            self.game_filter,
            self.config,
            self.store.registry,
            self.loc.t("all_games", "ALL GAMES"),
        )
        self._refresh_list()

    def _refresh_list(self) -> None:
        registry = self.store.registry
        game_id = selected_game_id(self.game_filter)
        mods = (
            registry.filter(game_id=game_id, query=self.search.text())
            if registry
            else []
        )
        current_id = self._current_mod().id if self.list.currentItem() else ""

        self.list.blockSignals(True)
        self.list.clear()
        for mod in mods:
            installed = is_mod_installed(self.config.install_dir_for(mod.game_id), mod.id)
            meta = f"{mod.author or self.loc.t('unknown', 'Unknown')} · {mod.version_label}"
            if game_id == ALL_GAMES:
                game = self.config.game(mod.game_id)
                meta += f" · {game.name if game else mod.game_id}"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, mod)
            item.setSizeHint(QSize(0, 62))
            self.list.addItem(item)
            self.list.setItemWidget(
                item,
                ModRow(
                    mod.name,
                    meta,
                    badge=self.loc.t("badge_installed", "Installed") if installed else "",
                ),
            )
            if mod.id == current_id:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        self.count_label.setText(f"{len(mods)} {self.loc.t('found', 'FOUND')}")

        if not mods:
            self._show_empty()
        elif self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def _info_cell(self, row: QHBoxLayout, title: str) -> QLabel:
        cell = QVBoxLayout()
        cell.setSpacing(2)
        label = QLabel(title.upper())
        label.setObjectName("statLabel")
        value = QLabel("—")
        value.setObjectName("infoValue")
        cell.addWidget(label)
        cell.addWidget(value)
        row.addLayout(cell, 1)
        return value

    def _show_empty(self) -> None:
        self.title_label.setText(self.loc.t("select_mod", "SELECT A MOD"))
        self.author_label.setText(
            self.loc.t(
                "nothing_selected",
                "Nothing selected yet — pick a mod from the list to preview it.",
            )
        )
        self.desc_label.clear()
        self.banner_label.clear_cover(self.loc.t("no_cover", "NO COVER"))
        self.icon_label.clear_cover("")
        self._clear_layout(self.tags_row)
        self.info_frame.hide()
        self.btn_install.setEnabled(False)
        self.btn_folder.hide()

    @staticmethod
    def _repolish(widget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # -- selection ----------------------------------------------------------
    def _current_mod(self) -> Mod | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_select(self, current: QListWidgetItem | None, previous=None) -> None:
        if current is None:
            self._show_empty()
            return

        mod: Mod = current.data(Qt.ItemDataRole.UserRole)
        install_root = self.config.install_dir_for(mod.game_id)
        installed = is_mod_installed(install_root, mod.id)

        game = self.config.game(mod.game_id)
        self.title_label.setText(mod.name)
        self.author_label.setText(
            f"{self.loc.t('by_author', 'by')} {mod.author or self.loc.t('unknown', 'Unknown')}"
            f"  ·  {mod.version_label}  ·  {game.name if game else mod.game_id}"
        )
        self.desc_label.setPlainText(mod.description or self.loc.t("no_description", "No description."))
        self.info_game.setText(game.name if game else mod.game_id)
        self.info_version.setText(mod.version_label)
        self.info_author.setText(mod.author or self.loc.t("unknown", "Unknown"))
        self.info_entry.setText(mod.entry_asset or "—")
        self.info_frame.show()
        self._clear_layout(self.tags_row)
        for tag in mod.tags[:6]:
            chip = QLabel(tag)
            chip.setObjectName("chip")
            self.tags_row.addWidget(chip)
        self.tags_row.addStretch()
        self.btn_install.setEnabled(mod.is_installable)
        self.btn_install.setText(
            self.loc.t("reinstall", "REINSTALL / UPDATE") if installed else self.loc.t("install", "INSTALL")
        )
        self.btn_install.setObjectName("" if installed else "primary")
        self._repolish(self.btn_install)

        self.btn_folder.setVisible(installed)
        self.btn_folder.setEnabled(installed)

        self.banner_label.clear_cover(
            self.loc.t("loading", "LOADING...")
            if mod.banner_url
            else self.loc.t("no_cover", "NO COVER")
        )
        self.icon_label.clear_cover("" if mod.icon_url else "")

        if mod.banner_url:
            self._load_image(mod, mod.banner_url, "banner")
        if mod.icon_url:
            self._load_image(mod, mod.icon_url, "icon")

    def _load_image(self, mod: Mod, url: str, tag: str) -> None:
        worker = ImageDownloader(url, tag, self)
        self._image_workers.append(worker)

        def on_loaded(loaded_tag: str, data: bytes) -> None:
            current = self._current_mod()
            if current is None or current.id != mod.id:
                return  # selection changed while the image was downloading
            if loaded_tag == "banner":
                if data.startswith(b"GIF8"):
                    self.banner_label.set_movie(data)
                else:
                    self.banner_label.set_cover(scale_pixmap(data, 720, 200))
            else:
                if data.startswith(b"GIF8"):
                    self.icon_label.set_movie(data)
                else:
                    self.icon_label.set_cover(scale_pixmap(data, 72, 72))

        def on_done() -> None:
            if worker in self._image_workers:
                self._image_workers.remove(worker)
            worker.deleteLater()

        worker.loaded.connect(on_loaded)
        worker.finished.connect(on_done)
        worker.start()

    # -- install ------------------------------------------------------------
    def _install(self) -> None:
        mod = self._current_mod()
        if mod is None or not mod.is_installable:
            return

        self.config.ensure_game(mod.game_id)
        self.config.save()
        install_root = self.config.install_dir_for(mod.game_id)

        dialog = UploadDialog(self, self.loc.t("install", "INSTALL"))
        dialog.set_status(self.loc.t("preparing", "Preparing..."), 0)
        worker = InstallWorker(mod, install_root, self)
        self._worker = worker

        worker.progress.connect(dialog.set_status)
        worker.succeeded.connect(lambda path: self._on_installed(mod, path, dialog))
        worker.failed.connect(lambda error: self._on_install_failed(error, dialog))
        worker.finished.connect(lambda: self._release_worker(worker))

        self.install_started.emit(mod.id)
        # Start only once the modal loop runs: a very fast install would otherwise
        # call dialog.accept() before exec() and block forever.
        QTimer.singleShot(0, worker.start)
        dialog.exec()

    def _release_worker(self, worker: InstallWorker) -> None:
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _on_installed(self, mod: Mod, path: str, dialog: UploadDialog) -> None:
        dialog.set_status(self.loc.t("installed_status", "Installed."), 100)
        dialog.accept()
        self.install_finished.emit(mod.id)
        if self.list.currentItem():
            self._on_select(self.list.currentItem())
        QMessageBox.information(
            self,
            self.loc.t("install", "INSTALL"),
            f"{mod.name} {mod.version_label} → {path}",
        )

    def _on_install_failed(self, error: str, dialog: UploadDialog) -> None:
        dialog.accept()
        self.install_finished.emit("")
        QMessageBox.critical(self, self.loc.t("error", "Error"), error)

    def _open_folder(self) -> None:
        mod = self._current_mod()
        if mod is None:
            return
        open_folder(self.config.install_dir_for(mod.game_id) / mod.id)


__all__ = ["CatalogTab"]
