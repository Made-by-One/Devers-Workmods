"""Installed tab: everything Workmods has put on disk, grouped by game."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from workmods.config import WorkmodsConfig
from workmods.i18n import Localization
from workmods.models import InstalledMod
from workmods.net import RegistryStore
from workmods.registry import ALL_GAMES
from workmods.storage import scan_installed_mods, uninstall_mod
from workmods.ui.common import populate_game_filter, selected_game_id
from workmods.ui.theme import load_icon
from workmods.ui.widgets import CoverLabel, ModRow, initial_pixmap
from workmods.utils import open_folder


class InstalledTab(QWidget):
    mods_changed = pyqtSignal(str)

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
        self._rows: dict[str, tuple[InstalledMod, Path]] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.section = QLabel(self.loc.t("installed_mods", "INSTALLED MODS"))
        self.section.setObjectName("sectionTitle")

        self.game_filter = QComboBox()
        self.game_filter.setMinimumWidth(190)
        self.game_filter.currentIndexChanged.connect(self.scan)

        btn_refresh = QPushButton(load_icon("refresh"), self.loc.t("refresh", "REFRESH"))
        btn_refresh.clicked.connect(self.scan)

        top.addWidget(self.section)
        top.addStretch()
        top.addWidget(self.game_filter)
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(14)
        splitter.setChildrenCollapsible(False)

        self.list = QListWidget()
        self.list.setSpacing(0)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.currentItemChanged.connect(self._on_select)
        self.list.setMinimumWidth(300)
        splitter.addWidget(self.list)

        self.detail = QFrame()
        self.detail.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(24, 24, 24, 24)
        detail_layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(16)
        self.detail_icon = CoverLabel(radius=16, placeholder="")
        self.detail_icon.setFixedSize(84, 84)
        header.addWidget(self.detail_icon, 0, Qt.AlignmentFlag.AlignTop)

        heading = QVBoxLayout()
        heading.setSpacing(4)
        self.detail_game = QLabel()
        self.detail_game.setObjectName("sectionTitle")
        self.detail_title = QLabel()
        self.detail_title.setObjectName("panelTitle")
        self.detail_meta = QLabel()
        self.detail_meta.setObjectName("meta")
        heading.addWidget(self.detail_game)
        heading.addWidget(self.detail_title)
        heading.addWidget(self.detail_meta)
        heading.addStretch()
        header.addLayout(heading, 1)

        self.detail_badge = QLabel(self.loc.t("badge_installed", "Installed").upper())
        self.detail_badge.setObjectName("chipAccent")
        header.addWidget(self.detail_badge, 0, Qt.AlignmentFlag.AlignTop)
        detail_layout.addLayout(header)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        detail_layout.addWidget(divider)

        self.description_label = QLabel(self.loc.t("description", "Description:").rstrip(":"))
        self.description_label.setObjectName("sectionTitle")
        self.detail_description = QLabel()
        self.detail_description.setObjectName("bodyText")
        self.detail_description.setWordWrap(True)
        detail_layout.addWidget(self.description_label)
        detail_layout.addWidget(self.detail_description)
        detail_layout.addSpacing(4)

        self.package_label = QLabel(self.loc.t("section_package", "PACKAGE"))
        self.package_label.setObjectName("sectionTitle")
        self.detail_path = QLabel()
        self.detail_path.setObjectName("dim")
        self.detail_path.setWordWrap(True)
        self.detail_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.package_label)
        detail_layout.addWidget(self.detail_path)
        self.detail_entry = QLabel()
        self.detail_entry.setObjectName("dim")
        detail_layout.addWidget(self.detail_entry)

        self.detail_hint = QLabel()
        self.detail_hint.setObjectName("emptyState")
        self.detail_hint.setWordWrap(True)
        detail_layout.addWidget(self.detail_hint)
        detail_layout.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_open = QPushButton(load_icon("folder"), self.loc.t("open_folder", "OPEN FOLDER"))
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_delete = QPushButton(
            load_icon("trash"), self.loc.t("delete", "DELETE").upper()
        )
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_delete)
        actions.addStretch()
        detail_layout.addLayout(actions)

        splitter.addWidget(self.detail)
        splitter.setSizes([380, 620])
        layout.addWidget(splitter, 1)

        populate_game_filter(
            self.game_filter, self.config, None, self.loc.t("all_games", "ALL GAMES")
        )
        self.scan()

    def refresh_games(self) -> None:
        populate_game_filter(
            self.game_filter,
            self.config,
            self.store.registry,
            self.loc.t("all_games", "ALL GAMES"),
        )
        self.scan()

    def scan(self) -> None:
        game_id = selected_game_id(self.game_filter)
        previous = self._selected_key()
        self._rows.clear()
        self.list.blockSignals(True)
        self.list.clear()

        rows: list[tuple[InstalledMod, Path]] = []
        for game, install_root in self.config.iter_game_dirs():
            if game_id not in (ALL_GAMES, game.id):
                continue
            for mod in scan_installed_mods(install_root, game.id):
                rows.append((mod, install_root))

        rows.sort(key=lambda row: (self.config.game_name(row[0].game_id), row[0].name.lower()))

        for mod, install_root in rows:
            game = self.config.game(mod.game_id)
            game_name = game.name if game else mod.game_id
            key = f"{mod.game_id}:{mod.mod_id}"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, 62))
            self.list.addItem(item)
            self.list.setItemWidget(
                item, ModRow(mod.display_name, f"{mod.version_label}  ·  {game_name}")
            )
            self._rows[key] = (mod, install_root)
            if key == previous:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)

        self.section.setText(
            f"{self.loc.t('installed_mods', 'INSTALLED MODS')} ({len(rows)})"
        )
        self.list.setVisible(bool(rows))
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._update_detail()

    def _selected_key(self) -> str:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _selected(self) -> tuple[InstalledMod, Path] | None:
        key = self._selected_key()
        return self._rows.get(key) if key else None

    def _on_select(self, current: QListWidgetItem | None, previous=None) -> None:
        self._update_detail()

    def _update_detail(self) -> None:
        selected = self._selected()
        if selected is None:
            self.detail_icon.clear_cover("")
            self.detail_game.setText("")
            self.detail_title.setText(self.loc.t("select_mod", "SELECT A MOD"))
            self.detail_meta.setText("")
            self.detail_badge.hide()
            self.package_label.hide()
            self.detail_path.setText("")
            self.detail_path.hide()
            self.description_label.hide()
            self.detail_description.setText("")
            self.detail_description.hide()
            self.detail_entry.setText("")
            self.detail_entry.hide()
            self.detail_hint.setText(
                self.loc.t(
                    "empty_installed",
                    "No mods installed for this profile.\n"
                    "Browse the catalog and hit Install to get started.",
                )
            )
            self.detail_hint.show()
            self.btn_open.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        mod, _install_root = selected
        game = self.config.game(mod.game_id)
        game_name = game.name if game else mod.game_id
        self.detail_icon.set_cover(initial_pixmap(mod.display_name, 84))
        self.detail_game.setText(game_name.upper())
        self.detail_title.setText(mod.display_name)
        self.detail_meta.setText(f"{mod.version_label}  ·  {mod.author or mod.mod_id}")
        self.detail_badge.show()
        self.detail_hint.hide()
        self.package_label.show()
        self.detail_path.setText(str(mod.path))
        self.detail_path.show()
        self.description_label.setVisible(bool(mod.description))
        self.detail_description.setText(mod.description)
        self.detail_description.setVisible(bool(mod.description))
        if mod.entry_asset:
            self.detail_entry.setText(
                f"{self.loc.t('entry_asset', 'Entry Asset:').rstrip(':')}: {mod.entry_asset}"
            )
            self.detail_entry.show()
        else:
            self.detail_entry.hide()
        self.btn_open.setEnabled(True)
        self.btn_delete.setEnabled(True)

    def _delete(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        mod, install_root = selected
        answer = QMessageBox.question(
            self,
            self.loc.t("delete", "Delete"),
            f"{self.loc.t('delete_confirm', 'Delete this mod folder?')}\n\n{mod.path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            uninstall_mod(install_root, mod.mod_id)
        except Exception as exc:
            QMessageBox.critical(self, self.loc.t("error", "Error"), str(exc))
            return
        self.scan()
        self.mods_changed.emit(mod.mod_id)

    def _open_folder(self) -> None:
        selected = self._selected()
        if selected is not None:
            open_folder(selected[0].path)


__all__ = ["InstalledTab"]
