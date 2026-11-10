"""Filesystem layer: packaging, hashing, safe install/remove and scanning.

Nothing here knows about Qt or GitHub, so it can be unit tested directly against
a temporary directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from workmods.models import DEFAULT_GAME_ID, InstalledMod, normalize_game_id

MANIFEST_NAME = ".devers_meta.json"
PUBLIC_MANIFEST_NAME = "workmod.json"
SKIPPED_DIRS = {".git", "__pycache__", ".idea", ".vscode"}
SKIPPED_FILES = {".DS_Store", "Thumbs.db", MANIFEST_NAME}
CHUNK_SIZE = 64 * 1024

ProgressCallback = Callable[[int, int], None]


class StorageError(RuntimeError):
    """Raised when a package cannot be built, installed or removed."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_mod(files_dir: str | Path, zip_path: str | Path) -> Path:
    """Zip the *contents* of ``files_dir`` into ``zip_path``.

    The archive root is the mod folder itself (no wrapper directory), because the
    client and the Unity SDK expect ``<mod_dir>/<file>`` after extraction.
    """
    files_dir = Path(files_dir)
    zip_path = Path(zip_path)
    if not files_dir.is_dir():
        raise StorageError(f"Mod files folder does not exist: {files_dir}")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    added = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(files_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
            for filename in sorted(files):
                if filename in SKIPPED_FILES:
                    continue
                file_path = Path(root) / filename
                if not file_path.is_file():
                    continue
                archive.write(file_path, file_path.relative_to(files_dir).as_posix())
                added += 1

    if added == 0:
        raise StorageError(f"No files to package in {files_dir}")
    return zip_path


def download_file(
    url: str,
    dest: str | Path,
    progress: ProgressCallback | None = None,
    timeout: int = 120,
) -> Path:
    """Stream ``url`` to ``dest`` (GitHub release assets redirect internally)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return dest


def _common_prefix(names: list[str]) -> str:
    """Return a wrapper directory shared by every entry, or ``""``."""
    if not names:
        return ""
    parts = [name.split("/", 1) for name in names]
    if any(len(part) < 2 for part in parts):
        return ""
    first = parts[0][0]
    if all(len(part) == 2 and part[0] == first for part in parts):
        return first
    return ""


def safe_extract(zip_path: str | Path, dest: str | Path) -> Path:
    """Extract an archive, rejecting path traversal and unwrapping one wrapper dir."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="workmods_extract_") as tmp:
        tmp_path = Path(tmp).resolve()
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                name = member.filename.replace("\\", "/")
                if not name or name.endswith("/"):
                    continue
                target = (tmp_path / name).resolve()
                if tmp_path not in target.parents:
                    raise StorageError(f"Archive entry escapes destination: {name}")
                archive.extract(member, tmp_path)

        entries = [p.relative_to(tmp_path).as_posix() for p in tmp_path.iterdir()]
        prefix = _common_prefix([e + ("/" if (tmp_path / e).is_dir() else "") for e in entries])
        source = (tmp_path / prefix) if prefix else tmp_path
        if not source.is_dir():
            source = tmp_path

        for item in sorted(source.iterdir()):
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
    return dest


def write_mod_meta(mod_dir: str | Path, meta: dict[str, Any]) -> Path:
    mod_dir = Path(mod_dir)
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / MANIFEST_NAME
    payload = dict(meta)
    payload.setdefault("installed_at", now_iso())
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return path


def read_mod_meta(mod_dir: str | Path) -> dict[str, Any]:
    """Read the client manifest, falling back to a mod-authored ``workmod.json``."""
    mod_dir = Path(mod_dir)
    for name in (MANIFEST_NAME, PUBLIC_MANIFEST_NAME):
        path = mod_dir / name
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                continue
    return {}


def install_package(
    zip_path: str | Path,
    install_root: str | Path,
    mod_id: str,
    meta: dict[str, Any] | None = None,
) -> Path:
    """Install a downloaded archive as ``install_root/mod_id`` (atomic replace)."""
    mod_id = str(mod_id).strip()
    if not mod_id or mod_id in {".", ".."} or "/" in mod_id or "\\" in mod_id:
        raise StorageError(f"Invalid mod id: {mod_id!r}")

    install_root = Path(install_root)
    install_root.mkdir(parents=True, exist_ok=True)
    target = install_root / mod_id
    staging = install_root / f".{mod_id}.installing"

    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    try:
        safe_extract(zip_path, staging)
        write_mod_meta(staging, {**(meta or {}), "id": mod_id})
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def uninstall_mod(install_root: str | Path, mod_id: str) -> bool:
    install_root = Path(install_root).resolve()
    target = (install_root / mod_id).resolve()
    if target == install_root or install_root not in target.parents:
        raise StorageError("Refusing to delete a path outside the install directory")
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def is_mod_installed(install_root: str | Path, mod_id: str) -> bool:
    return (Path(install_root) / mod_id).is_dir()


def scan_installed_mods(install_root: str | Path, game_id: str = DEFAULT_GAME_ID) -> list[InstalledMod]:
    """List installed mod folders, newest manifest fields first."""
    install_root = Path(install_root)
    if not install_root.is_dir():
        return []
    game_id = normalize_game_id(game_id)
    mods: list[InstalledMod] = []
    for entry in sorted(install_root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        meta = read_mod_meta(entry)
        mods.append(
            InstalledMod(
                mod_id=str(meta.get("id") or entry.name),
                path=str(entry),
                game_id=str(meta.get("game_id") or game_id),
                name=str(meta.get("name") or entry.name),
                version=str(meta.get("version") or ""),
                author=str(meta.get("author") or ""),
                description=str(meta.get("description") or ""),
                entry_asset=str(meta.get("entry_asset") or ""),
                manifest=meta,
            )
        )
    return mods


__all__ = [
    "MANIFEST_NAME", "PUBLIC_MANIFEST_NAME", "StorageError", "download_file",
    "install_package", "is_mod_installed", "now_iso", "package_mod", "read_mod_meta",
    "safe_extract", "scan_installed_mods", "sha256_file", "uninstall_mod",
    "write_mod_meta",
]
