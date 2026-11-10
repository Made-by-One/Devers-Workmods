"""Settings: registry, language, and one game profile per target game."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from workmods.config import CONFIG_DIR, WorkmodsConfig, default_mods_dir
from workmods.i18n import Localization, get_available_languages
from workmods.models import DEFAULT_GAME_ID, Game, normalize_game_id
from workmods.ui.theme import load_icon
from workmods.utils import open_folder


class GameDialog(QDialog):
    """Create or edit one game profile."""

    def __init__(self, parent: QWidget | None = None, game: Game | None = None):
        super().__init__(parent)
        self.setWindowTitle("Game Profile")
        self.resize(520, 220)
        self._game = game

        self.id_input = QLineEdit(game.id if game else "")
        self.id_input.setPlaceholderText("space-rangers")
        self.id_input.setDisabled(bool(game and game.id == DEFAULT_GAME_ID))
        self.name_input = QLineEdit(game.name if game else "")
        self.name_input.setPlaceholderText("Space Rangers")
        self.dir_input = QLineEdit(game.install_dir if game else "")
        self.dir_input.setPlaceholderText(str(default_mods_dir("space-rangers")))

        browse = QPushButton("BROWSE...")
        browse.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.dir_input)
        dir_row.addWidget(browse)

        form = QFormLayout()
        form.addRow("Game ID:", self.id_input)
        form.addRow("Display Name:", self.name_input)
        form.addRow("Install Directory:", dir_row)

        buttons = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        cancel.clicked.connect(self.reject)
        save = QPushButton("SAVE")
        save.setObjectName("primary")
        save.clicked.connect(self._accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select install directory")
        if directory:
            self.dir_input.setText(directory)

    def _accept(self) -> None:
        if not self.id_input.text().strip():
            QMessageBox.warning(self, "Error", "Game ID is required.")
            return
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Display name is required.")
            return
        self.accept()

    def result_game(self) -> Game:
        game_id = normalize_game_id(self.id_input.text())
        return Game(
            id=game_id,
            name=self.name_input.text().strip(),
            install_dir=self.dir_input.text().strip() or default_mods_dir(game_id),
        )


class SettingsTab(QWidget):
    configuration_changed = pyqtSignal()

    def __init__(self, config: WorkmodsConfig, loc: Localization, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self.loc = loc
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        title = QLabel(self.loc.t("settings", "SETTINGS"))
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        registry_row = QHBoxLayout()
        self.registry_input = QLineEdit(self.config.registry_url)
        save_registry = QPushButton("SAVE")
        save_registry.clicked.connect(self._save_registry)
        registry_row.addWidget(QLabel("REGISTRY URL"))
        registry_row.addWidget(self.registry_input, 1)
        registry_row.addWidget(save_registry)
        layout.addLayout(registry_row)

        lang_row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(get_available_languages())
        self.lang_combo.setCurrentText(self.config.language)
        self.lang_combo.currentTextChanged.connect(self._save_language)
        lang_row.addWidget(QLabel(self.loc.t("language", "LANGUAGE")))
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        active_row = QHBoxLayout()
        self.active_game_combo = QComboBox()
        self.active_game_combo.setMinimumWidth(240)
        self.active_game_combo.currentIndexChanged.connect(self._save_active_game)
        active_row.addWidget(QLabel(self.loc.t("active_game", "ACTIVE GAME")))
        active_row.addWidget(self.active_game_combo)
        active_row.addStretch()
        layout.addLayout(active_row)

        layout.addWidget(QLabel(self.loc.t("games", "GAME PROFILES")))
        self.games_list = QListWidget()
        layout.addWidget(self.games_list, 1)

        game_buttons = QHBoxLayout()
        add_btn = QPushButton(load_icon("edit"), self.loc.t("add_game", "ADD GAME"))
        add_btn.clicked.connect(self._add_game)
        edit_btn = QPushButton(load_icon("edit"), self.loc.t("edit_game", "EDIT GAME"))
        edit_btn.clicked.connect(self._edit_game)
        remove_btn = QPushButton(load_icon("trash"), self.loc.t("remove_game", "REMOVE GAME"))
        remove_btn.setObjectName("danger")
        remove_btn.clicked.connect(self._remove_game)
        game_buttons.addWidget(add_btn)
        game_buttons.addWidget(edit_btn)
        game_buttons.addWidget(remove_btn)
        game_buttons.addStretch()

        config_btn = QPushButton(load_icon("folder"), "CONFIG FOLDER")
        config_btn.clicked.connect(lambda: open_folder(CONFIG_DIR))
        game_buttons.addWidget(config_btn)
        layout.addLayout(game_buttons)

        self.reload_games()

    # -- rendering ----------------------------------------------------------
    def reload_games(self) -> None:
        active_id = self.config.active_game_id

        self.active_game_combo.blockSignals(True)
        self.active_game_combo.clear()
        for game in self.config.games:
            self.active_game_combo.addItem(game.display_name, game.id)
        self.active_game_combo.setCurrentIndex(
            max(self.active_game_combo.findData(active_id), 0)
        )
        self.active_game_combo.blockSignals(False)

        self.games_list.clear()
        for game in self.config.games:
            item = QListWidgetItem(
                f"{game.display_name}  →  {self.config.install_dir_for(game.id)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, game.id)
            self.games_list.addItem(item)

    # -- persistence --------------------------------------------------------
    def _save_registry(self) -> None:
        self.config.registry_url = self.registry_input.text().strip()
        self.config.save()
        self.configuration_changed.emit()

    def _save_language(self, language: str) -> None:
        self.config.language = language
        self.config.save()

    def _save_active_game(self, _index: int = 0) -> None:
        game_id = self.active_game_combo.currentData()
        if not game_id:
            return
        self.config.active_game_id = game_id
        self.config.save()
        self.configuration_changed.emit()

    def _add_game(self) -> None:
        dialog = GameDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        game = dialog.result_game()
        self.config.add_game(game)
        self.config.ensure_game(game.id)
        self.config.save()
        self.reload_games()
        self.configuration_changed.emit()

    def _edit_game(self) -> None:
        game_id = self._selected_game_id()
        game = self.config.game(game_id)
        if game is None:
            return

        dialog = GameDialog(self, game)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.result_game()

        if updated.id != game.id:
            if game.id == DEFAULT_GAME_ID:
                QMessageBox.warning(self, "Error", "The default profile id cannot change.")
                return
            if self.config.game(updated.id):
                QMessageBox.warning(self, "Error", f"Game '{updated.id}' already exists.")
                return
            if self.config.active_game_id == game.id:
                self.config.active_game_id = updated.id
            game.id = updated.id
        game.name = updated.name
        game.install_dir = updated.install_dir
        self.config.save()
        self.reload_games()
        self.configuration_changed.emit()

    def _remove_game(self) -> None:
        game_id = self._selected_game_id()
        if not game_id or game_id == DEFAULT_GAME_ID:
            QMessageBox.information(self, "Info", "The default profile cannot be removed.")
            return
        if not self.config.remove_game(game_id):
            return
        self.config.save()
        self.reload_games()
        self.configuration_changed.emit()

    def _selected_game_id(self) -> str:
        item = self.games_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole))


__all__ = ["GameDialog", "SettingsTab"]
