"""Mod editor: metadata, local save, publish to GitHub and unpublish."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMovie, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
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
from workmods.i18n import Localization
from workmods.models import Mod, normalize_game_id
from workmods.publisher import PublishRequest
from workmods.storage import read_mod_meta, write_mod_meta
from workmods.ui.widgets import ElidedLabel, UploadDialog
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
        loc: Localization | None = None,
    ):
        super().__init__(parent)
        self.loc = loc or Localization("en")
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

        self.setWindowTitle(self.loc.t("mod_editor", "Mod Editor"))
        self.setMinimumSize(960, 620)
        self.resize(980, 720)
        self._build_ui()
        self._load_existing()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel(self.loc.t("mod_editor", "Mod Editor"))
        title.setObjectName("panelTitle")
        id_chip = QLabel(self.mod.id)
        id_chip.setObjectName("chip")
        header.addWidget(title)
        header.addWidget(id_chip)
        header.addStretch()
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(16)

        self.repo_combo = QComboBox()
        self.repo_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.repo_combo.setMinimumContentsLength(20)
        self.repo_combo.addItem(self.loc.t("local_only", "Local Only (No Repo)"), "")
        for repo in self.repos:
            name = repo["full_name"] if isinstance(repo, dict) else str(repo)
            self.repo_combo.addItem(name, name)

        self.id_input = QLineEdit(self.mod.id)
        self.id_input.setDisabled(True)

        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.game_combo.setMinimumContentsLength(24)
        self.game_combo.setToolTip(
            self.loc.t(
                "target_game_tooltip",
                "Target game. Pick a configured profile or type a new game id.\n"
                "The mod is installed into that game's install directory.",
            )
        )
        for game in self.config.games:
            self.game_combo.addItem(game.display_name, game.id)
        if self.game_combo.findData(self.mod.game_id) < 0:
            self.game_combo.addItem(self.mod.game_id, self.mod.game_id)
        self.game_combo.setCurrentIndex(max(self.game_combo.findData(self.mod.game_id), 0))
        if self.game_combo.lineEdit() is not None:
            self.game_combo.lineEdit().setCursorPosition(0)

        self.name_input = QLineEdit(self.mod.name if self.mod.name != self.mod.id else "")
        self.author_input = QLineEdit(self.author)
        self.author_input.setPlaceholderText(
            self.loc.t("author_placeholder", "Your name / GitHub handle")
        )

        self.desc_input = QTextEdit()
        self.desc_input.setPlainText(self.mod.description)
        self.desc_input.setMinimumHeight(132)

        self.version_input = QLineEdit(self.mod.version or "1.0.0")
        self.tags_input = QLineEdit(", ".join(self.mod.tags))
        self.tags_input.setPlaceholderText(self.loc.t("tags_placeholder", "shaders, weapons, ui"))
        self.entry_asset_input = QLineEdit(self.mod.entry_asset)
        self.entry_asset_input.setPlaceholderText(
            self.loc.t("entry_asset_placeholder", "Optional default asset name for the Unity SDK")
        )

        preview_style = (
            "border: 1px solid #2a2a3b; border-radius: 10px; "
            "background: #0b0b13; color: #6f6f88;"
        )
        self.icon_preview = QLabel(self.loc.t("no_icon", "No Icon"))
        self.icon_preview.setFixedSize(76, 76)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setStyleSheet(preview_style)
        self.banner_preview = QLabel(self.loc.t("no_banner", "No Banner"))
        self.banner_preview.setMinimumSize(260, 96)
        self.banner_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.banner_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_preview.setStyleSheet(preview_style)

        self.btn_icon = QPushButton(self.loc.t("select_icon", "SELECT ICON"))
        self.btn_icon.clicked.connect(lambda: self._pick_image("icon"))
        self.btn_banner = QPushButton(self.loc.t("select_banner", "SELECT BANNER"))
        self.btn_banner.clicked.connect(lambda: self._pick_image("banner"))
        self.btn_files = QPushButton(self.loc.t("select_mod_files", "SELECT MOD FILES FOLDER"))
        self.btn_files.clicked.connect(self._pick_files_folder)
        for button in (self.btn_icon, self.btn_banner, self.btn_files):
            button.setMinimumHeight(34)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(self.loc.t("repository", "GitHub Repository:"), self.repo_combo)
        form.addRow(self.loc.t("mod_id_auto", "Mod ID (Auto):"), self.id_input)
        form.addRow(self.loc.t("target_game", "Target Game:"), self.game_combo)
        form.addRow(self.loc.t("mod_name", "Mod Name:"), self.name_input)
        form.addRow(self.loc.t("author_label", "Author:"), self.author_input)
        form.addRow(self.loc.t("version", "Version:"), self.version_input)
        form.addRow(self.loc.t("tags", "Tags:"), self.tags_input)
        form.addRow(self.loc.t("entry_asset", "Entry Asset:"), self.entry_asset_input)
        for field in (
            self.repo_combo,
            self.id_input,
            self.game_combo,
            self.name_input,
            self.author_input,
            self.version_input,
            self.tags_input,
            self.entry_asset_input,
        ):
            label = form.labelForField(field)
            if label is not None:
                label.setObjectName("fieldLabel")

        details_card = QFrame()
        details_card.setObjectName("card")
        details_box = QVBoxLayout(details_card)
        details_box.setContentsMargins(18, 16, 18, 16)
        details_box.setSpacing(14)
        details_title = QLabel(self.loc.t("section_details", "MOD DETAILS"))
        details_title.setObjectName("sectionTitle")
        details_box.addWidget(details_title)
        details_box.addLayout(form)
        details_box.addStretch()

        media_card = QFrame()
        media_card.setObjectName("card")
        media_box = QVBoxLayout(media_card)
        media_box.setContentsMargins(18, 16, 18, 16)
        media_box.setSpacing(12)
        media_title = QLabel(self.loc.t("section_media", "DESCRIPTION & MEDIA"))
        media_title.setObjectName("sectionTitle")
        media_box.addWidget(media_title)

        desc_title = QLabel(self.loc.t("description", "Description:"))
        desc_title.setObjectName("fieldLabel")
        media_box.addWidget(desc_title)
        media_box.addWidget(self.desc_input)

        media_row = QHBoxLayout()
        media_row.setSpacing(12)
        icon_col = QVBoxLayout()
        icon_col.setSpacing(8)
        icon_col.addWidget(self.icon_preview)
        icon_col.addWidget(self.btn_icon)
        self.icon_name_label = ElidedLabel("")
        self.icon_name_label.setObjectName("meta")
        icon_col.addWidget(self.icon_name_label)
        banner_col = QVBoxLayout()
        banner_col.setSpacing(8)
        banner_col.addWidget(self.banner_preview)
        banner_col.addWidget(self.btn_banner)
        self.banner_name_label = ElidedLabel("")
        self.banner_name_label.setObjectName("meta")
        banner_col.addWidget(self.banner_name_label)
        media_row.addLayout(icon_col)
        media_row.addLayout(banner_col, 1)
        media_box.addLayout(media_row)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        media_box.addWidget(divider)

        package_title = QLabel(self.loc.t("section_package", "PACKAGE"))
        package_title.setObjectName("sectionTitle")
        media_box.addWidget(package_title)
        media_box.addWidget(self.btn_files)
        media_box.addStretch()

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(details_card, 1)
        columns.addWidget(media_card, 1)
        layout.addLayout(columns)
        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save_btn = QPushButton(self.loc.t("save_mod", "SAVE MOD"))
        save_btn.clicked.connect(self.save_mod)

        self.btn_publish = QPushButton(
            self.loc.t("update_github", "UPDATE ON GITHUB")
            if self.is_published
            else self.loc.t("publish_request", "PUBLISH & REQUEST ADDITION")
        )
        self.btn_publish.setObjectName("primary")
        self.btn_publish.clicked.connect(self.publish_mod)

        self.btn_unpublish = QPushButton(self.loc.t("unpublish", "UNPUBLISH"))
        self.btn_unpublish.setObjectName("danger")
        self.btn_unpublish.clicked.connect(self.unpublish_mod)
        self.btn_unpublish.setVisible(self.is_published)

        buttons.addWidget(self.btn_unpublish)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(self.btn_publish)
        outer.addLayout(buttons)

    def _load_existing(self) -> None:
        if not self.mod.id:
            return
        target = self.config.install_dir_for(self._original_game_id) / self.mod.id
        icon_name = self._find_saved_image(target, "icon")
        if icon_name:
            self.icon_path = str(target / icon_name)
            self._set_image_preview(self.icon_preview, self.icon_path, (76, 76))
            self.icon_name_label.setText(icon_name)
        banner_name = self._find_saved_image(target, "banner")
        if banner_name:
            self.banner_path = str(target / banner_name)
            self._set_image_preview(self.banner_preview, self.banner_path, (300, 100))
            self.banner_name_label.setText(banner_name)

    # -- field helpers ------------------------------------------------------
    def selected_game_id(self) -> str:
        data = self.game_combo.currentData()
        if data:
            return normalize_game_id(data)
        return normalize_game_id(self.game_combo.currentText())

    def selected_repo(self) -> str:
        data = self.repo_combo.currentData()
        return str(data or "").strip()

    _IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".ico")

    def _find_saved_image(self, folder: Path, kind: str) -> str | None:
        for extension in self._IMAGE_EXTENSIONS:
            candidate = folder / f"{kind}{extension}"
            if candidate.is_file():
                return candidate.name
        return None

    def _set_image_preview(self, label: QLabel, filename: str, size: tuple[int, int]) -> None:
        previous = getattr(label, "_movie", None)
        if previous is not None:
            previous.stop()
        label.setMovie(None)
        if filename.lower().endswith(".gif"):
            movie = QMovie(filename)
            label._movie = movie
            label.setMovie(movie)
            movie.start()
            label.setText("")
            return
        label._movie = None
        pixmap = QPixmap(filename).scaled(
            size[0], size[1], Qt.AspectRatioMode.KeepAspectRatio
        )
        label.setPixmap(pixmap)

    def _pick_image(self, kind: str) -> None:
        title = self.loc.t("select_icon" if kind == "icon" else "select_banner")
        filename, _ = QFileDialog.getOpenFileName(
            self, title, "", "Images (*.png *.jpg *.jpeg *.gif *.ico)"
        )
        if not filename:
            return
        if kind == "icon":
            self.icon_path = filename
            self._set_image_preview(self.icon_preview, filename, (76, 76))
            self.icon_name_label.setText(Path(filename).name)
        else:
            self.banner_path = filename
            self._set_image_preview(self.banner_preview, filename, (300, 100))
            self.banner_name_label.setText(Path(filename).name)

    def _pick_files_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self.loc.t("select_mod_files", "SELECT MOD FILES FOLDER")
        )
        if directory:
            self.mod_files_dir = directory
            self.btn_files.setText(f"{Path(directory).name}")
            self._import_manifest(directory)

    def _import_manifest(self, directory: str) -> None:
        """Prefill empty fields from a mod-authored ``workmod.json``."""
        manifest = read_mod_meta(directory)
        if not manifest:
            return
        imported = False
        if not self.name_input.text().strip() and manifest.get("name"):
            self.name_input.setText(str(manifest["name"]))
            imported = True
        current_version = self.version_input.text().strip()
        if manifest.get("version") and current_version in ("", "1.0.0"):
            self.version_input.setText(str(manifest["version"]))
            imported = True
        if not self.author_input.text().strip() and manifest.get("author"):
            self.author_input.setText(str(manifest["author"]))
            imported = True
        if not self.desc_input.toPlainText().strip() and manifest.get("description"):
            self.desc_input.setPlainText(str(manifest["description"]))
            imported = True
        if not self.entry_asset_input.text().strip() and manifest.get("entry_asset"):
            self.entry_asset_input.setText(str(manifest["entry_asset"]))
            imported = True
        if not self.tags_input.text().strip() and manifest.get("tags"):
            tags = manifest["tags"]
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            self.tags_input.setText(", ".join(str(tag) for tag in tags))
            imported = True
        game_id = normalize_game_id(manifest.get("game_id"))
        if manifest.get("game_id") and self.game_combo.findData(game_id) < 0:
            self.game_combo.addItem(game_id, game_id)
        if manifest.get("game_id") and self.selected_game_id() != game_id:
            index = self.game_combo.findData(game_id)
            if index >= 0 and self.mod.game_id == self._original_game_id:
                self.game_combo.setCurrentIndex(index)
                imported = True
        if imported:
            self.btn_files.setToolTip(self.loc.t("imported_metadata", "Imported metadata from workmod.json."))

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
            raise ValueError(self.loc.t("mod_id_missing", "Mod id is missing."))
        name = self.name_input.text().strip()
        if not name:
            raise ValueError(self.loc.t("name_required", "Mod Name is required."))

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
                raise ValueError(
                    f"{self.loc.t('mod_exists', 'A different mod already exists at this path. Delete it first.')}\n{target}"
                )
            if target.exists():
                target.rmdir()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_target), str(target))
        target.mkdir(parents=True, exist_ok=True)

        # Replace any previously saved icon/banner so a changed format (for
        # example PNG -> GIF) does not leave a stale file behind.
        for kind in ("icon", "banner"):
            for old in target.glob(f"{kind}.*"):
                if old.is_file() and old.suffix.lower() in self._IMAGE_EXTENSIONS:
                    old.unlink()

        if self.icon_path and os.path.isfile(self.icon_path):
            suffix = Path(self.icon_path).suffix.lower()
            if suffix not in self._IMAGE_EXTENSIONS:
                suffix = ".png"
            destination = (target / f"icon{suffix}").resolve()
            if Path(self.icon_path).resolve() != destination:
                shutil.copy(self.icon_path, destination)
        if self.banner_path and os.path.isfile(self.banner_path):
            suffix = Path(self.banner_path).suffix.lower()
            if suffix not in self._IMAGE_EXTENSIONS:
                suffix = ".png"
            destination = (target / f"banner{suffix}").resolve()
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
            "icon_path": self._find_saved_image(target, "icon") or "",
            "banner_path": self._find_saved_image(target, "banner") or "",
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
            QMessageBox.critical(
                self,
                self.loc.t("error", "Error"),
                f"{self.loc.t('save_failed', 'Failed to save mod:')}\n{exc}",
            )
            return
        self.saved.emit(self.mod.id)
        QMessageBox.information(
            self,
            self.loc.t("saved", "Saved"),
            f"{self.loc.t('saved', 'Saved')}:\n{target}",
        )

    # -- publishing ---------------------------------------------------------
    def publish_mod(self) -> None:
        if not self.config.github_token:
            QMessageBox.warning(
                self, self.loc.t("error", "Error"), self.loc.t("login_first", "Log in with GitHub first.")
            )
            return

        if not self.name_input.text().strip():
            QMessageBox.warning(
                self,
                self.loc.t("error", "Error"),
                self.loc.t("name_required", "Mod Name is required."),
            )
            return
        if not self.version_input.text().strip():
            QMessageBox.warning(
                self,
                self.loc.t("error", "Error"),
                self.loc.t("version_required", "Version is required."),
            )
            return

        request = self._collect_request()
        if not request.repo:
            QMessageBox.warning(
                self,
                self.loc.t("error", "Error"),
                self.loc.t("select_repo_error", "Select a GitHub repository for this mod."),
            )
            return
        if not self.mod_files_dir or not Path(self.mod_files_dir).is_dir():
            QMessageBox.warning(
                self,
                self.loc.t("error", "Error"),
                self.loc.t("select_files_error", "Select a folder with mod files first."),
            )
            return

        try:
            self._persist()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.loc.t("error", "Error"),
                f"{self.loc.t('save_before_publish_failed', 'Failed to save the mod before publishing:')}\n{exc}",
            )
            return

        dialog = UploadDialog(self, self.loc.t("publishing", "Publishing"))
        dialog.set_status(self.loc.t("preparing", "Preparing..."), 0)
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
        dialog.set_status(self.loc.t("published_status", "Published."), 100)
        dialog.accept()
        self.is_published = True
        self.btn_unpublish.setVisible(True)
        self.published.emit(self.mod.id)
        QMessageBox.information(
            self,
            self.loc.t("success", "Success"),
            f"{self.loc.t('publish_success', 'Mod published to your repository.')}\n\n"
            f"{self.loc.t('release', 'Release:')} {result.release_url or result.download_url}\n"
            f"{self.loc.t('pull_request', 'Registry pull request:')} "
            f"{result.pr_url or self.loc.t('not_created', '(not created)')}\n"
            f"SHA-256: {result.sha256}\n\n"
            f"{self.loc.t('publish_success_note', 'A maintainer reviews the submission; once the pull request is merged the registry rebuilds automatically and the mod appears in the catalog.')}",
        )

    def _on_publish_failed(self, error: str, dialog: UploadDialog) -> None:
        dialog.accept()
        QMessageBox.critical(
            self, self.loc.t("error", "Error"), f"{self.loc.t('failed_publish', 'Failed to publish:')}\n{error}"
        )

    def unpublish_mod(self) -> None:
        if not self.config.github_token:
            return
        answer = QMessageBox.question(
            self,
            self.loc.t("unpublish", "UNPUBLISH"),
            self.loc.t(
                "unpublish_confirm",
                "Open a pull request that removes this mod from the shared registry?\n\n"
                "Your GitHub repository, files and release stay online.",
            ),
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
        worker.failed.connect(
            lambda error: QMessageBox.critical(self, self.loc.t("error", "Error"), error)
        )
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
            self.loc.t("removal_requested", "Removal requested"),
            f"{self.loc.t('removal_created', 'Removal pull request created:')}\n"
            f"{pr_url or self.loc.t('see_registry_repo', '(see the registry repository)')}\n\n"
            f"{self.loc.t('removal_note', 'The mod disappears from the catalog after a maintainer merges it.')}",
        )


__all__ = ["ModEditorDialog"]
