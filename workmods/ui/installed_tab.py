"""Installed tab: everything Workmods has put on disk, grouped by game."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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
from workmods.ui.widgets import ModRow
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
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.game_filter = QComboBox()
        self.game_filter.setMinimumWidth(190)
        self.game_filter.currentIndexChanged.connect(self.scan)

        btn_refresh = QPushButton(load_icon("refresh"), self.loc.t("refresh", "REFRESH"))
        btn_refresh.clicked.connect(self.scan)

        top.addWidget(self.game_filter)
        top.addWidget(btn_refresh)
        top.addStretch()
        layout.addLayout(top)

        self.section = QLabel(self.loc.t("installed_mods", "INSTALLED MODS"))
        self.section.setObjectName("sectionTitle")
        layout.addWidget(self.section)

        self.list = QListWidget()
        self.list.setSpacing(0)
        layout.addWidget(self.list, 1)

        self.empty_label = QLabel(
            self.loc.t(
                "empty_installed",
                "No mods installed for this profile.\nBrowse the catalog and hit Install to get started.",
            )
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_del = QPushButton(load_icon("trash"), self.loc.t("delete_selected", "DELETE SELECTED"))
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete)

        self.btn_folder = QPushButton(load_icon("folder"), "")
        self.btn_folder.setToolTip(self.loc.t("open_folder", "Open Mod Folder"))
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setFixedWidth(46)

        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(self.btn_folder)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        populate_game_filter(self.game_filter, self.config, None, self.loc.t("all_games", "ALL GAMES"))
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
        self._rows.clear()
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

        self.list.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
        self.section.setText(
            f"{self.loc.t('installed_mods', 'INSTALLED MODS')} ({len(rows)})"
        )

    def _selected(self) -> tuple[InstalledMod, Path] | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return self._rows.get(item.data(Qt.ItemDataRole.UserRole))

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
