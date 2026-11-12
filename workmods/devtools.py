"""Developer tooling for mod authors: scaffold, validate and pack a mod.

Everything here is Qt-free, so it can be used from the desktop app, a shell or
CI. The manifest format is the same ``workmod.json`` the SDK and the publisher
already understand.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workmods.models import DEFAULT_GAME_ID, normalize_game_id
from workmods.storage import StorageError, package_mod, sha256_file

MANIFEST_NAME = "workmod.json"
VERSION_MAX_LENGTH = 64


class DevToolsError(RuntimeError):
    """Raised when a mod folder cannot be scaffolded, read or packed."""


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings)}


@dataclass
class PackResult:
    path: Path
    sha256: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "sha256": self.sha256, "size": self.size}


def new_mod_id() -> str:
    """Stable-looking, short id used as the mod's identity."""
    return uuid.uuid4().hex[:8]


def version_problem(version: str) -> str | None:
    version = str(version or "").strip()
    if not version:
        return "version is required"
    if len(version) > VERSION_MAX_LENGTH:
        return f"version may not exceed {VERSION_MAX_LENGTH} characters"
    if any(ch in version for ch in " /\\"):
        return "version may not contain spaces or slashes"
    return None


def read_manifest(folder: str | Path) -> dict[str, Any]:
    path = Path(folder) / MANIFEST_NAME
    if not path.is_file():
        raise DevToolsError(f"{MANIFEST_NAME} not found in {folder}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise DevToolsError(f"{MANIFEST_NAME} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DevToolsError(f"{MANIFEST_NAME} must contain a JSON object")
    return data


def scaffold_mod(
    target: str | Path,
    *,
    name: str = "",
    game_id: str = DEFAULT_GAME_ID,
    author: str = "",
    version: str = "1.0.0",
    entry_asset: str = "",
    tags: list[str] | None = None,
    force: bool = False,
) -> Path:
    """Create a mod folder with a ready-to-edit ``workmod.json``."""
    target = Path(target)
    problem = version_problem(version)
    if problem:
        raise DevToolsError(problem)
    manifest_path = target / MANIFEST_NAME
    if manifest_path.exists() and not force:
        raise DevToolsError(f"{manifest_path} already exists (use --force to overwrite)")
    target.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "id": new_mod_id(),
        "game_id": normalize_game_id(game_id),
        "name": name.strip() or target.resolve().name,
        "version": version.strip(),
        "author": author.strip(),
        "description": "",
        "entry_asset": entry_asset.strip(),
        "bundles": [],
        "tags": list(tags or []),
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return manifest_path


def validate_mod(folder: str | Path) -> ValidationResult:
    """Check a mod folder before publishing; warnings are advice, not blockers."""
    folder = Path(folder)
    result = ValidationResult()
    if not folder.is_dir():
        result.errors.append(f"folder does not exist: {folder}")
        return result

    try:
        manifest = read_manifest(folder)
    except DevToolsError as exc:
        result.errors.append(str(exc))
        return result

    name = str(manifest.get("name") or "").strip()
    if not name:
        result.errors.append("name is required")

    version = str(manifest.get("version") or "").strip()
    problem = version_problem(version)
    if problem:
        result.errors.append(problem)

    raw_id = str(manifest.get("id") or "").strip()
    if raw_id and any(ch in raw_id for ch in "/\\"):
        result.errors.append("id may not contain slashes")
    if not raw_id:
        result.warnings.append("no id in workmod.json; the client generates one when publishing")

    game_id = str(manifest.get("game_id") or "").strip()
    if not game_id:
        result.warnings.append("no game_id; the mod will target the default profile")
    elif normalize_game_id(game_id) != game_id:
        result.warnings.append(
            f"game_id will be normalized to '{normalize_game_id(game_id)}'"
        )

    bundles = manifest.get("bundles") or []
    if isinstance(bundles, str):
        bundles = [part.strip() for part in bundles.split(",") if part.strip()]
    if not isinstance(bundles, list):
        result.errors.append("bundles must be a list of relative paths")
        bundles = []
    for bundle in bundles:
        relative = str(bundle).strip()
        if not relative:
            continue
        candidate = (folder / relative).resolve()
        if folder.resolve() not in candidate.parents:
            result.errors.append(f"bundle escapes the mod folder: {relative}")
        elif not candidate.is_file():
            result.errors.append(f"bundle listed but missing: {relative}")

    content = [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME and not path.name.startswith(".")
    ]
    if not content:
        result.errors.append("the folder has no mod files")
    if not (folder / "icon.png").is_file() and not (folder / "icon.jpg").is_file():
        result.warnings.append("no icon.png (optional, but the catalog looks better with one)")
    if not (folder / "banner.png").is_file() and not (folder / "banner.jpg").is_file():
        result.warnings.append("no banner.png (optional)")
    if not str(manifest.get("entry_asset") or "").strip():
        result.warnings.append("no entry_asset; players must pick the asset themselves")
    return result


def pack_mod(folder: str | Path, output: str | Path | None = None) -> PackResult:
    """Package a mod folder exactly like the publisher does and hash the ZIP."""
    folder = Path(folder)
    if not folder.is_dir():
        raise DevToolsError(f"folder does not exist: {folder}")
    destination = Path(output) if output else folder.parent / f"{folder.name}.zip"
    try:
        package_mod(folder, destination)
    except StorageError as exc:
        raise DevToolsError(str(exc)) from exc
    return PackResult(
        path=destination,
        sha256=sha256_file(destination),
        size=destination.stat().st_size,
    )


__all__ = [
    "DevToolsError",
    "MANIFEST_NAME",
    "PackResult",
    "ValidationResult",
    "new_mod_id",
    "pack_mod",
    "read_manifest",
    "scaffold_mod",
    "validate_mod",
    "version_problem",
]
