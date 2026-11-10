"""Publish / unpublish orchestration.

One publish is five steps and four of them can fail for unrelated reasons, so the
sequence lives here instead of inside a Qt dialog:

    package -> hash -> upload files to repo -> release + asset -> registry dispatch

The UI only listens to ``progress`` and shows the resulting payload.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from workmods.config import BOT_SECRET, REGISTRY_REPO
from workmods.github_api import GitHubClient, GitHubError
from workmods.models import DEFAULT_GAME_ID, normalize_game_id
from workmods.storage import StorageError, now_iso, package_mod, sha256_file

ProgressCallback = Callable[[int, str], None]


def _has_file(path: str | Path | None) -> bool:
    return bool(path) and Path(path).is_file()


@dataclass
class PublishRequest:
    """Everything needed to publish one mod version."""

    repo: str
    files_dir: str
    mod_id: str
    name: str
    version: str
    game_id: str = DEFAULT_GAME_ID
    description: str = ""
    author: str = ""
    entry_asset: str = ""
    tags: list[str] = field(default_factory=list)
    icon_path: str = ""
    banner_path: str = ""
    registry_repo: str = REGISTRY_REPO
    bot_secret: str = BOT_SECRET

    def __post_init__(self) -> None:
        self.repo = (self.repo or "").strip().strip("/")
        self.mod_id = (self.mod_id or "").strip()
        self.version = (self.version or "").strip()
        self.game_id = normalize_game_id(self.game_id)


@dataclass
class PublishResult:
    payload: dict[str, Any]
    sha256: str
    download_url: str
    release_url: str = ""


class ModPublisher:
    def __init__(
        self,
        client: GitHubClient,
        progress: ProgressCallback | None = None,
        work_dir: str | Path | None = None,
    ):
        self.client = client
        self.progress = progress
        self.work_dir = Path(work_dir) if work_dir else None

    def _report(self, value: int, message: str) -> None:
        if self.progress:
            self.progress(value, message)

    def validate(self, request: PublishRequest) -> None:
        if not self.client.token:
            raise StorageError("Not logged in to GitHub.")
        if not request.repo:
            raise StorageError("Select a GitHub repository first.")
        if not request.mod_id:
            raise StorageError("Mod id is required.")
        if not request.version:
            raise StorageError("Version is required.")
        if not Path(request.files_dir).is_dir():
            raise StorageError("Select a folder with the mod files first.")
        if len(request.version) > 64 or any(ch in request.version for ch in " /\\"):
            raise StorageError("Version may not contain spaces or slashes.")

    def publish(self, request: PublishRequest) -> PublishResult:
        self.validate(request)

        temp_dir = self.work_dir
        cleanup = False
        if temp_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="workmods_publish_"))
            cleanup = True
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f"{request.mod_id}.zip"

        try:
            self._report(8, "Packing mod files...")
            package_mod(request.files_dir, zip_path)

            self._report(20, "Calculating SHA-256...")
            digest = sha256_file(zip_path)

            repo_data = self.client.get_repo(request.repo)
            branch = str(repo_data.get("default_branch") or "main")

            self._report(30, "Uploading files to the repository...")
            self._upload_files(request, branch)

            tag = f"v{request.version}"
            self._report(55, f"Creating release {tag}...")
            release = self.client.ensure_release(
                request.repo,
                tag,
                body=f"{request.name} {tag}\n\nPublished with Workmods.",
            )
            release_url = str(release.get("html_url") or "")

            self._report(68, "Uploading ZIP to the release...")
            self.client.upload_release_asset(
                release["upload_url"], f"{request.mod_id}.zip", zip_path
            )

            download_url = (
                f"https://github.com/{request.repo}/releases/download/{tag}/{request.mod_id}.zip"
            )
            payload = self._build_payload(request, digest, download_url, branch)

            self._report(85, "Sending to the registry...")
            self.client.dispatch("add_mod", payload, request.registry_repo)

            self._report(100, "Published.")
            return PublishResult(
                payload={k: v for k, v in payload.items() if k != "secret"},
                sha256=digest,
                download_url=download_url,
                release_url=release_url,
            )
        finally:
            if cleanup:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _upload_files(self, request: PublishRequest, branch: str) -> None:
        files_dir = Path(request.files_dir)
        files = [p for p in sorted(files_dir.rglob("*")) if p.is_file()]
        total = max(len(files), 1)
        for index, path in enumerate(files, start=1):
            rel = path.relative_to(files_dir).as_posix()
            self.client.put_file(
                request.repo,
                rel,
                path.read_bytes(),
                f"Update {rel} ({request.name} v{request.version})",
            )
            self._report(30 + int(20 * index / total), f"Uploaded {rel}")

        for kind, source in (("icon", request.icon_path), ("banner", request.banner_path)):
            if source and Path(source).is_file():
                self.client.put_file(
                    request.repo,
                    f"{kind}.png",
                    Path(source).read_bytes(),
                    f"Update {kind} for {request.name}",
                )

    def _build_payload(
        self,
        request: PublishRequest,
        digest: str,
        download_url: str,
        branch: str,
    ) -> dict[str, Any]:
        raw = f"https://raw.githubusercontent.com/{request.repo}/{branch}"
        payload: dict[str, Any] = {
            "secret": request.bot_secret,
            "id": request.mod_id,
            "game_id": request.game_id,
            "name": request.name or request.mod_id,
            "version": request.version,
            "author": request.author or "",
            "description": request.description,
            "repo": request.repo,
            "sha256": digest,
            "download_url": download_url,
            "entry_asset": request.entry_asset,
            "tags": list(request.tags),
            "updated_at": now_iso(),
            "icon_url": f"{raw}/icon.png" if _has_file(request.icon_path) else "",
            "banner_url": f"{raw}/banner.png" if _has_file(request.banner_path) else "",
        }
        return payload

    def unpublish(self, mod_id: str, registry_repo: str = REGISTRY_REPO, bot_secret: str = BOT_SECRET) -> None:
        if not mod_id:
            raise StorageError("Mod id is required.")
        if not self.client.token:
            raise StorageError("Not logged in to GitHub.")
        self._report(20, "Removing mod from the registry...")
        self.client.dispatch(
            "remove_mod",
            {"secret": bot_secret, "id": mod_id},
            registry_repo,
        )
        self._report(100, "Removed from the registry.")


__all__ = ["GitHubError", "ModPublisher", "PublishRequest", "PublishResult"]
