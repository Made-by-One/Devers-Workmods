"""Author studio: GitHub login, local mod drafts, publishing."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from workmods.config import WorkmodsConfig
from workmods.github_api import GitHubClient
from workmods.i18n import Localization
from workmods.models import InstalledMod, Mod
from workmods.net import RegistryStore
from workmods.oauth import OAuthServerThread, authorize_url
from workmods.storage import scan_installed_mods, uninstall_mod
from workmods.ui.editor_dialog import ModEditorDialog
from workmods.ui.theme import load_icon, scale_pixmap
from workmods.ui.widgets import ImageDownloader, ModRow
from workmods.ui.workers import ProfileWorker
from workmods.utils import open_folder


class AuthorStudioTab(QWidget):
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
        self.user_data: dict = {}
        self.user_repos: list[dict] = []
        self._rows: dict[str, tuple[InstalledMod, Path]] = {}
        self._profile_worker: ProfileWorker | None = None
        self._avatar_worker: ImageDownloader | None = None
        self._oauth: OAuthServerThread | None = None
        self._build_ui()

        self.store.loaded.connect(lambda _registry: self.refresh_data())
        if self.config.github_token:
            self._fetch_profile()
        self.refresh_data()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        account_card = QFrame()
        account_card.setObjectName("card")
        account_box = QVBoxLayout(account_card)
        account_box.setContentsMargins(18, 14, 18, 14)
        account_box.setSpacing(10)
        account_title = QLabel("ACCOUNT")
        account_title.setObjectName("sectionTitle")
        account_box.addWidget(account_title)

        auth_layout = QHBoxLayout()
        auth_layout.setSpacing(12)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setStyleSheet("border-radius: 20px; background: #333;")
        self.avatar_label.hide()

        self.auth_label = QLabel("Not Logged In")
        self.auth_label.setObjectName("rowTitle")

        self.btn_auth = QPushButton(load_icon("web"), "LOGIN VIA GITHUB")
        self.btn_auth.clicked.connect(self._login)
        self.btn_logout = QPushButton("LOGOUT")
        self.btn_logout.clicked.connect(self._logout)
        self.btn_logout.hide()

        auth_layout.addWidget(self.avatar_label)
        auth_layout.addWidget(self.auth_label)
        auth_layout.addStretch()
        auth_layout.addWidget(self.btn_auth)
        auth_layout.addWidget(self.btn_logout)
        account_box.addLayout(auth_layout)
        layout.addWidget(account_card)

        self.section = QLabel("MY MODS")
        self.section.setObjectName("sectionTitle")
        layout.addWidget(self.section)

        self.mod_list = QListWidget()
        self.mod_list.setSpacing(0)
        layout.addWidget(self.mod_list, 1)

        self.empty_label = QLabel(
            "No local mods yet.\nCreate a mod, publish it as a pull request and it will show up here."
        )
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.btn_new_repo = QPushButton(load_icon("web"), "NEW REPO")
        self.btn_new_repo.setToolTip("Create a new repository on GitHub")
        self.btn_new_repo.clicked.connect(self._create_repo)

        self.btn_create = QPushButton(load_icon("edit"), "CREATE")
        self.btn_create.clicked.connect(self._create_mod)

        self.btn_edit = QPushButton(load_icon("edit"), "EDIT")
        self.btn_edit.clicked.connect(self._edit_mod)

        self.btn_folder = QPushButton(load_icon("folder"), "")
        self.btn_folder.setToolTip("Open Mod Folder")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_folder.setFixedWidth(40)

        self.btn_delete = QPushButton(load_icon("trash"), "DELETE")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_mod)

        self.btn_create.setObjectName("primary")
        self.btn_folder.setFixedWidth(46)
        # QSS padding is not part of the style hint, so short labels get clipped.
        for button in (
            self.btn_new_repo,
            self.btn_create,
            self.btn_edit,
            self.btn_delete,
        ):
            button.setMinimumWidth(button.sizeHint().width() + 18)

        btn_layout.addWidget(self.btn_new_repo)
        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_folder)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._apply_auth_state()

    def _apply_auth_state(self) -> None:
        logged_in = bool(self.user_data)
        has_token = bool(self.config.github_token)
        self.btn_auth.setEnabled(not has_token)
        self.btn_auth.setVisible(not logged_in)
        self.btn_logout.setVisible(logged_in)
        self.avatar_label.setVisible(logged_in and not self.avatar_label.pixmap().isNull())
        self.btn_new_repo.setEnabled(logged_in)
        self.btn_create.setEnabled(logged_in)
        self.btn_edit.setEnabled(logged_in)
        if self.user_data:
            self.auth_label.setText(f"Logged in as: {self.user_data.get('login', '?')}")
        elif has_token:
            self.auth_label.setText("Checking session...")
            self.btn_auth.setVisible(False)
            self.btn_logout.setVisible(True)
        else:
            self.auth_label.setText("Not Logged In (Read Only)")

    # -- account ------------------------------------------------------------
    def _login(self) -> None:
        self.btn_auth.setText("WAITING FOR BROWSER...")
        self.btn_auth.setEnabled(False)

        self._oauth = OAuthServerThread(parent=self)
        self._oauth.auth_success.connect(self._on_auth_success)
        self._oauth.auth_failed.connect(self._on_auth_failed)
        self._oauth.start()
        webbrowser.open(authorize_url())

    def _on_auth_success(self, token: str) -> None:
        self.config.github_token = token
        self.config.save()
        self.btn_auth.setText("LOGIN VIA GITHUB")
        self.btn_auth.setEnabled(True)
        self._fetch_profile()

    def _on_auth_failed(self, message: str) -> None:
        self.btn_auth.setText("LOGIN VIA GITHUB")
        self.btn_auth.setEnabled(True)
        QMessageBox.critical(self, "Login failed", message)

    def _fetch_profile(self) -> None:
        token = self.config.github_token
        if not token:
            return
        self._profile_worker = ProfileWorker(token, self)
        self._profile_worker.succeeded.connect(self._on_profile)
        self._profile_worker.failed.connect(self._on_profile_error)
        self._profile_worker.finished.connect(self._release_profile_worker)
        self._profile_worker.start()

    def _release_profile_worker(self) -> None:
        if self._profile_worker is not None:
            self._profile_worker.deleteLater()
            self._profile_worker = None

    def _on_profile(self, user: dict, repos: list) -> None:
        self.user_data = user or {}
        self.user_repos = repos or []
        self._apply_auth_state()
        avatar_url = self.user_data.get("avatar_url")
        if avatar_url:
            self._avatar_worker = ImageDownloader(avatar_url, "avatar", self)
            self._avatar_worker.loaded.connect(self._on_avatar)
            self._avatar_worker.start()

    def _on_avatar(self, _tag: str, data: bytes) -> None:
        self.avatar_label.setPixmap(scale_pixmap(data, 40, 40))
        self.avatar_label.show()

    def _on_profile_error(self, message: str) -> None:
        if "401" in message or "authenticated" in message.lower():
            self._logout(silent=True)
            self.auth_label.setText("Session expired — log in again.")
            return
        self.auth_label.setText(f"Error: {message}")

    def _logout(self, silent: bool = False) -> None:
        self.config.github_token = ""
        self.config.save()
        self.user_data = {}
        self.user_repos = []
        self.avatar_label.clear()
        self._apply_auth_state()
        if not silent:
            QMessageBox.information(self, "Logout", "Logged out successfully.")

    def _create_repo(self) -> None:
        if not self.config.github_token:
            return
        name, ok = QInputDialog.getText(self, "New Repository", "Repository Name:")
        if not ok or not name.strip():
            return
        try:
            GitHubClient(self.config.github_token).create_repo(name.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Success", "Repository created successfully!")
        self._fetch_profile()

    # -- my mods ------------------------------------------------------------
    def refresh_data(self) -> None:
        published_ids = (
            set(self.store.registry.mods_by_id()) if self.store.registry else set()
        )

        rows: list[tuple[InstalledMod, Path]] = []
        for _game, install_root in self.config.iter_game_dirs():
            for mod in scan_installed_mods(install_root, _game.id):
                rows.append((mod, install_root))
        rows.sort(key=lambda row: (row[0].game_id, row[0].name.lower()))

        previous = self._selected_key()
        self._rows.clear()
        self.mod_list.blockSignals(True)
        self.mod_list.clear()
        for mod, install_root in rows:
            published = mod.mod_id in published_ids
            key = f"{mod.game_id}:{mod.mod_id}"
            game = self.config.game(mod.game_id)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, 62))
            self.mod_list.addItem(item)
            self.mod_list.setItemWidget(
                item,
                ModRow(
                    mod.display_name,
                    f"{mod.version_label}  ·  {game.name if game else mod.game_id}",
                    badge="Published" if published else "Local",
                ),
            )
            self._rows[key] = (mod, install_root)
            if key == previous:
                self.mod_list.setCurrentItem(item)
        self.mod_list.blockSignals(False)
        self.mod_list.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
        self.section.setText(f"MY MODS ({len(rows)})")

    def _selected_key(self) -> str:
        item = self.mod_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _selected(self) -> tuple[InstalledMod, Path] | None:
        key = self._selected_key()
        return self._rows.get(key) if key else None

    def _mod_from_installed(self, mod: InstalledMod) -> Mod:
        manifest = mod.manifest or {}
        return Mod(
            id=mod.mod_id,
            game_id=mod.game_id,
            name=mod.name,
            version=mod.version,
            author=mod.author,
            description=mod.description,
            repo=str(manifest.get("repo") or ""),
            entry_asset=mod.entry_asset,
            tags=manifest.get("tags") or [],
        )

    def _is_published(self, mod_id: str) -> bool:
        return bool(self.store.registry and mod_id in self.store.registry.mods_by_id())

    def _create_mod(self) -> None:
        dialog = ModEditorDialog(
            self.config,
            self,
            repos=self.user_repos,
            author=str(self.user_data.get("login") or ""),
        )
        dialog.saved.connect(self._on_mod_changed)
        dialog.published.connect(self._on_mod_changed)
        dialog.exec()
        self.refresh_data()

    def _edit_mod(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        installed, _install_root = selected
        dialog = ModEditorDialog(
            self.config,
            self,
            mod=self._mod_from_installed(installed),
            repos=self.user_repos,
            is_published=self._is_published(installed.mod_id),
            author=str(self.user_data.get("login") or installed.author),
        )
        dialog.saved.connect(self._on_mod_changed)
        dialog.published.connect(self._on_mod_changed)
        dialog.exec()
        self.refresh_data()

    def _on_mod_changed(self, mod_id: str) -> None:
        self.refresh_data()
        self.mods_changed.emit(mod_id)

    def _delete_mod(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        mod, install_root = selected
        answer = QMessageBox.question(
            self,
            "Delete",
            f"Delete '{mod.mod_id}' locally?\n\n{mod.path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            uninstall_mod(install_root, mod.mod_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh_data()
        self.mods_changed.emit(mod.mod_id)

    def _open_folder(self) -> None:
        selected = self._selected()
        if selected is not None:
            open_folder(selected[0].path)


__all__ = ["AuthorStudioTab"]
