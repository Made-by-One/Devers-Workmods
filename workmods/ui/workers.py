"""Background workers for network/file operations.

Qt threads emit plain signals; the widgets own them and keep a reference until
``succeeded``/``failed`` fires, otherwise the QThread would be garbage collected
mid-flight.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from workmods.github_api import GitHubClient
from workmods.models import DEFAULT_GAME_ID, Mod
from workmods.publisher import ModPublisher, PublishRequest, PublishResult
from workmods.storage import download_file, install_package, sha256_file


class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(str)  # installed directory
    failed = pyqtSignal(str)

    def __init__(self, mod: Mod, install_root: str | Path, parent=None):
        super().__init__(parent)
        self.mod = mod
        self.install_root = Path(install_root)

    def run(self) -> None:  # noqa: D401 - Qt entry point
        tmp_dir = Path(tempfile.mkdtemp(prefix="workmods_install_"))
        zip_path = tmp_dir / f"{self.mod.id}.zip"
        try:
            if not self.mod.download_url:
                raise ValueError("This mod has no download URL in the registry.")
            self.progress.emit(5, f"Downloading {self.mod.name}...")

            def on_chunk(done: int, total: int) -> None:
                if total:
                    self.progress.emit(5 + int(65 * done / total), f"Downloading... {done * 100 // total}%")

            download_file(self.mod.download_url, zip_path, progress=on_chunk)

            if self.mod.sha256:
                self.progress.emit(75, "Verifying SHA-256...")
                actual = sha256_file(zip_path)
                if actual.lower() != self.mod.sha256.lower():
                    raise ValueError(
                        "Checksum mismatch — the download may be corrupted or tampered with."
                    )

            self.progress.emit(85, "Installing files...")
            meta = {
                "id": self.mod.id,
                "game_id": self.mod.game_id,
                "name": self.mod.name,
                "version": self.mod.version,
                "author": self.mod.author,
                "description": self.mod.description,
                "entry_asset": self.mod.entry_asset,
                "tags": self.mod.tags,
                "repo": self.mod.repo,
                "sha256": self.mod.sha256,
                "download_url": self.mod.download_url,
            }
            target = install_package(zip_path, self.install_root, self.mod.id, meta)
            self.progress.emit(100, "Installed.")
            self.succeeded.emit(str(target))
        except Exception as exc:  # surfaced to the user as a dialog
            self.failed.emit(str(exc))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class PublishWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)  # PublishResult
    failed = pyqtSignal(str)

    def __init__(self, token: str, request: PublishRequest, parent=None):
        super().__init__(parent)
        self.client = GitHubClient(token)
        self.request = request

    def run(self) -> None:
        try:
            publisher = ModPublisher(
                self.client, progress=lambda value, text: self.progress.emit(value, text)
            )
            result: PublishResult = publisher.publish(self.request)
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class UnpublishWorker(QThread):
    succeeded = pyqtSignal(str)  # pull request URL
    failed = pyqtSignal(str)

    def __init__(
        self,
        token: str,
        mod_id: str,
        game_id: str = DEFAULT_GAME_ID,
        registry_repo: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.token = token
        self.mod_id = mod_id
        self.game_id = game_id
        self.registry_repo = registry_repo

    def run(self) -> None:
        try:
            publisher = ModPublisher(GitHubClient(self.token))
            kwargs = {"registry_repo": self.registry_repo} if self.registry_repo else {}
            pr_url = publisher.unpublish(self.mod_id, game_id=self.game_id, **kwargs)
            self.succeeded.emit(pr_url)
        except Exception as exc:
            self.failed.emit(str(exc))


class ProfileWorker(QThread):
    """Fetch the authenticated user and their repositories in one round trip."""

    succeeded = pyqtSignal(dict, list)  # user, repos
    failed = pyqtSignal(str)

    def __init__(self, token: str, parent=None):
        super().__init__(parent)
        self.client = GitHubClient(token)

    def run(self) -> None:
        try:
            self.succeeded.emit(self.client.get_user(), self.client.list_repos())
        except Exception as exc:
            self.failed.emit(str(exc))


__all__ = ["InstallWorker", "ProfileWorker", "PublishWorker", "UnpublishWorker"]
