"""Mod editor: metadata, local save, publish to GitHub and unpublish."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from workmods.config import REGISTRY_REPO, WorkmodsConfig
from workmods.models import Mod, normalize_game_id
from workmods.publisher import PublishRequest
from workmods.storage import write_mod_meta
from workmods.ui.widgets import UploadDialog
from workmods.ui.workers import PublishWorker, UnpublishWorker


class ModEditorDialog(QDialog):
    saved = pyqtSignal(str)
    published = pyqtSignal(str)

    def __init__(
        self,
        config: WorkmodsConfig,
        parent: QWidget | None = None,
        mod: Mod | None = None,
        repos: list[str] | None = None,
        is_published: bool = False,
        author: str = "",
    ):
        super().__init__(parent)
        self.config = config
        self.mod = mod or Mod(id=str(uuid.uuid4())[:8])
        self.repos = repos or []
        self.is_published = is_published
        self.author = author or self.mod.author
        self.icon_path = ""
        self.banner_path = ""
        self.mod_files_dir = ""
        self._original_game_id = self.mod.game_id
        self._publish_worker: PublishWorker | None = None
        self._unpublish_worker: UnpublishWorker | None = None

        self.setWindowTitle("Mod Editor")
        self.resize(560, 840)
        self._build_ui()
        self._load_existing()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        self.repo_combo = QComboBox()
        self.repo_combo.addItem("Local Only (No Repo)", "")
        for repo in self.repos:
            name = repo["full_name"] if isinstance(repo, dict) else str(repo)
            self.repo_combo.addItem(name, name)

        self.id_input = QLineEdit(self.mod.id)
        self.id_input.setDisabled(True)

        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.setToolTip(
            "Target game. Pick a configured profile or type a new game id.\n"
            "The mod is installed into that game's install directory."
        )
        for game in self.config.games:
            self.game_combo.addItem(game.display_name, game.id)
        if self.game_combo.findData(self.mod.game_id) < 0:
            self.game_combo.addItem(self.mod.game_id, self.mod.game_id)
        self.game_combo.setCurrentIndex(max(self.game_combo.findData(self.mod.game_id), 0))

        self.name_input = QLineEdit(self.mod.name if self.mod.name != self.mod.id else "")
        self.author_input = QLineEdit(self.author)
        self.author_input.setPlaceholderText("Your name / GitHub handle")

        self.desc_input = QTextEdit()
        self.desc_input.setPlainText(self.mod.description)
        self.desc_input.setFixedHeight(110)

        self.version_input = QLineEdit(self.mod.version or "1.0.0")
        self.tags_input = QLineEdit(", ".join(self.mod.tags))
        self.tags_input.setPlaceholderText("shaders, weapons, ui")
        self.entry_asset_input = QLineEdit(self.mod.entry_asset)
        self.entry_asset_input.setPlaceholderText("Optional default asset name for the Unity SDK")

        preview_style = (
            "border: 1px solid #262636; border-radius: 10px; "
            "background: #0c0c14; color: #6f6f88;"
        )
        self.icon_preview = QLabel("No Icon")
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setStyleSheet(preview_style)
        self.banner_preview = QLabel("No Banner")
        self.banner_preview.setFixedSize(300, 100)
        self.banner_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_preview.setStyleSheet(preview_style)

        self.btn_icon = QPushButton("SELECT ICON")
        self.btn_icon.clicked.connect(lambda: self._pick_image("icon"))
        self.btn_banner = QPushButton("SELECT BANNER")
        self.btn_banner.clicked.connect(lambda: self._pick_image("banner"))
        self.btn_files = QPushButton("SELECT MOD FILES FOLDER")
        self.btn_files.clicked.connect(self._pick_files_folder)
        for button in (self.btn_icon, self.btn_banner, self.btn_files):
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("GitHub Repository:", self.repo_combo)
        form.addRow("Mod ID (Auto):", self.id_input)
        form.addRow("Target Game:", self.game_combo)
        form.addRow("Mod Name:", self.name_input)
        form.addRow("Author:", self.author_input)
        form.addRow("Description:", self.desc_input)
        form.addRow("Version:", self.version_input)
        form.addRow("Tags:", self.tags_input)
        form.addRow("Entry Asset:", self.entry_asset_input)
        form.addRow("Icon:", self.btn_icon)
        form.addRow("Preview:", self.icon_preview)
        form.addRow("Banner:", self.btn_banner)
        form.addRow("Preview:", self.banner_preview)
        form.addRow("Files Folder:", self.btn_files)

        layout.addLayout(form)
        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save_btn = QPushButton("SAVE MOD")
        save_btn.clicked.connect(self.save_mod)

        self.btn_publish = QPushButton(
            "UPDATE ON GITHUB" if self.is_published else "PUBLISH & REQUEST ADDITION"
        )
        self.btn_publish.setObjectName("primary")
        self.btn_publish.clicked.connect(self.publish_mod)

        self.btn_unpublish = QPushButton("UNPUBLISH")
        self.btn_unpublish.setObjectName("danger")
        self.btn_unpublish.clicked.connect(self.unpublish_mod)
        self.btn_unpublish.setVisible(self.is_published)

        buttons.addWidget(save_btn)
        buttons.addWidget(self.btn_publish)
        buttons.addWidget(self.btn_unpublish)
        buttons.addStretch()
        outer.addLayout(buttons)

    def _load_existing(self) -> None:
        if not self.mod.id:
            return
        target = self.config.install_dir_for(self._original_game_id) / self.mod.id
        if (target / "icon.png").is_file():
            self.icon_path = str(target / "icon.png")
            self.icon_preview.setPixmap(
                QPixmap(self.icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
            )
            self.btn_icon.setText("ICON: icon.png")
        if (target / "banner.png").is_file():
            self.banner_path = str(target / "banner.png")
            self.banner_preview.setPixmap(
                QPixmap(self.banner_path).scaled(300, 100, Qt.AspectRatioMode.KeepAspectRatio)
            )
            self.btn_banner.setText("BANNER: banner.png")

    # -- field helpers ------------------------------------------------------
    def selected_game_id(self) -> str:
        data = self.game_combo.currentData()
        if data:
            return normalize_game_id(data)
        return normalize_game_id(self.game_combo.currentText())

    def selected_repo(self) -> str:
        data = self.repo_combo.currentData()
        return str(data or "").strip()

    def _pick_image(self, kind: str) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, f"Select {kind}", "", "Images (*.png *.jpg *.jpeg *.ico)"
        )
        if not filename:
            return
        if kind == "icon":
            self.icon_path = filename
            self.icon_preview.setPixmap(
                QPixmap(filename).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
            )
            self.btn_icon.setText(f"ICON: {Path(filename).name}")
        else:
            self.banner_path = filename
            self.banner_preview.setPixmap(
                QPixmap(filename).scaled(300, 100, Qt.AspectRatioMode.KeepAspectRatio)
            )
            self.btn_banner.setText(f"BANNER: {Path(filename).name}")

    def _pick_files_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Folder with Mod Files")
        if directory:
            self.mod_files_dir = directory
            self.btn_files.setText(f"FILES: {Path(directory).name}")

    def _collect_request(self) -> PublishRequest:
        return PublishRequest(
            repo=self.selected_repo(),
            files_dir=self.mod_files_dir,
            mod_id=self.mod.id,
            name=self.name_input.text().strip() or self.mod.id,
            version=self.version_input.text().strip(),
            game_id=self.selected_game_id(),
            description=self.desc_input.toPlainText().strip(),
            author=self.author_input.text().strip(),
            entry_asset=self.entry_asset_input.text().strip(),
            tags=[t.strip() for t in self.tags_input.text().split(",") if t.strip()],
            icon_path=self.icon_path,
            banner_path=self.banner_path,
            registry_repo=REGISTRY_REPO,
        )

    # -- local save ---------------------------------------------------------
    def _persist(self) -> Path:
        mod_id = self.id_input.text().strip()
        if not mod_id:
            raise ValueError("Mod id is missing.")
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Mod Name is required.")

        game_id = self.selected_game_id()
        self.config.ensure_game(game_id)
        install_root = self.config.install_dir_for(game_id)
        target = install_root / mod_id

        # The mod moved to another game profile: relocate the folder instead of
        # leaving a stale copy behind in the old game's directory.
        old_root = self.config.install_dir_for(self._original_game_id)
        old_target = old_root / mod_id
        if (
            self._original_game_id != game_id
            and old_target.is_dir()
            and old_target.resolve() != target.resolve()
        ):
            if target.exists() and any(target.iterdir()):
                raise ValueError(f"A different mod already exists at {target}. Delete it first.")
            if target.exists():
                target.rmdir()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_target), str(target))
        target.mkdir(parents=True, exist_ok=True)

        if self.icon_path and os.path.isfile(self.icon_path):
            destination = (target / "icon.png").resolve()
            if Path(self.icon_path).resolve() != destination:
                shutil.copy(self.icon_path, destination)
        if self.banner_path and os.path.isfile(self.banner_path):
            destination = (target / "banner.png").resolve()
            if Path(self.banner_path).resolve() != destination:
                shutil.copy(self.banner_path, destination)

        meta = {
            "id": mod_id,
            "game_id": game_id,
            "name": name,
            "description": self.desc_input.toPlainText().strip(),
            "version": self.version_input.text().strip(),
            "author": self.author_input.text().strip(),
            "entry_asset": self.entry_asset_input.text().strip(),
            "tags": [t.strip() for t in self.tags_input.text().split(",") if t.strip()],
            "repo": self.selected_repo(),
            "icon_path": "icon.png" if (target / "icon.png").is_file() else "",
            "banner_path": "banner.png" if (target / "banner.png").is_file() else "",
            "mod_files_dir": self.mod_files_dir,
        }
        write_mod_meta(target, meta)
        self.config.save()
        self._original_game_id = game_id
        return target

    def save_mod(self) -> None:
        try:
            target = self._persist()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save mod:\n{exc}")
            return
        self.saved.emit(self.mod.id)
        QMessageBox.information(self, "Saved", f"Mod saved to:\n{target}")

    # -- publishing ---------------------------------------------------------
    def publish_mod(self) -> None:
        if not self.config.github_token:
            QMessageBox.warning(self, "Error", "Log in with GitHub first.")
            return

        request = self._collect_request()
        if not request.repo:
            QMessageBox.warning(self, "Error", "Select a GitHub repository for this mod.")
            return
        if not self.mod_files_dir or not Path(self.mod_files_dir).is_dir():
            QMessageBox.warning(self, "Error", "Select a folder with mod files first.")
            return

        try:
            self._persist()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save the mod before publishing:\n{exc}")
            return

        dialog = UploadDialog(self, "Publishing")
        dialog.set_status("Preparing...", 0)
        worker = PublishWorker(self.config.github_token, request, self)
        self._publish_worker = worker
        worker.progress.connect(dialog.set_status)
        worker.succeeded.connect(lambda result: self._on_published(result, dialog))
        worker.failed.connect(lambda error: self._on_publish_failed(error, dialog))
        worker.finished.connect(lambda: self._release_publish_worker(worker))
        QTimer.singleShot(0, worker.start)
        dialog.exec()

    def _release_publish_worker(self, worker: PublishWorker) -> None:
        if self._publish_worker is worker:
            self._publish_worker = None
        worker.deleteLater()

    def _on_published(self, result, dialog: UploadDialog) -> None:
        dialog.set_status("Published.", 100)
        dialog.accept()
        self.is_published = True
        self.btn_unpublish.setVisible(True)
        self.published.emit(self.mod.id)
        QMessageBox.information(
            self,
            "Success",
            "Mod published to your repository.\n\n"
            f"Release: {result.release_url or result.download_url}\n"
            f"Registry pull request: {result.pr_url or '(not created)'}\n"
            f"SHA-256: {result.sha256}\n\n"
            "A maintainer reviews the submission; once the pull request is merged "
            "the registry rebuilds automatically and the mod appears in the catalog.",
        )

    def _on_publish_failed(self, error: str, dialog: UploadDialog) -> None:
        dialog.accept()
        QMessageBox.critical(self, "Error", f"Failed to publish:\n{error}")

    def unpublish_mod(self) -> None:
        if not self.config.github_token:
            return
        answer = QMessageBox.question(
            self,
            "Unpublish",
            "Open a pull request that removes this mod from the shared registry?\n\n"
            "Your GitHub repository, files and release stay online.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        worker = UnpublishWorker(
            self.config.github_token,
            self.mod.id,
            self.selected_game_id(),
            parent=self,
        )
        self._unpublish_worker = worker
        worker.succeeded.connect(self._on_unpublished)
        worker.failed.connect(lambda error: QMessageBox.critical(self, "Error", error))
        worker.finished.connect(lambda: self._release_unpublish_worker(worker))
        worker.start()

    def _release_unpublish_worker(self, worker: UnpublishWorker) -> None:
        if self._unpublish_worker is worker:
            self._unpublish_worker = None
        worker.deleteLater()

    def _on_unpublished(self, pr_url: str = "") -> None:
        self.is_published = False
        self.btn_unpublish.setVisible(False)
        self.published.emit(self.mod.id)
        QMessageBox.information(
            self,
            "Removal requested",
            "Removal pull request created:\n"
            f"{pr_url or '(see the registry repository)'}\n\n"
            "The mod disappears from the catalog after a maintainer merges it.",
        )


__all__ = ["ModEditorDialog"]
