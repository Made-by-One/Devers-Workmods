"""Developer tooling for mod authors: scaffold, validate and pack a mod.

Everything here is Qt-free, so it can be used from the desktop app, a shell or
CI. The manifest format is the same ``workmod.json`` the SDK and the publisher
already understand.
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workmods.config import APP_VERSION
from workmods.models import DEFAULT_GAME_ID, normalize_game_id
from workmods.storage import StorageError, package_mod, safe_extract, sha256_file

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


def validate_mod(folder: str | Path, *, compatibility: Any = None) -> ValidationResult:
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
    if not any((folder / f"icon{ext}").is_file() for ext in (".png", ".jpg", ".jpeg", ".gif", ".ico")):
        result.warnings.append("no icon.png (optional, but the catalog looks better with one)")
    if not any((folder / f"banner{ext}").is_file() for ext in (".png", ".jpg", ".jpeg", ".gif", ".ico")):
        result.warnings.append("no banner.png (optional)")
    if not str(manifest.get("entry_asset") or "").strip():
        result.warnings.append("no entry_asset; players must pick the asset themselves")
    _validate_compatibility(result, manifest, compatibility)
    return result


def validate_package(
    package: str | Path,
    *,
    expected_sha256: str | None = None,
    max_size_bytes: int = 100 * 1024 * 1024,
    compatibility: Any = None,
) -> ValidationResult:
    """Validate a packaged mod (directory or ZIP) before it is published or installed."""
    package = Path(package)
    result = ValidationResult()
    if not package.exists():
        result.errors.append(f"package does not exist: {package}")
        return result

    if package.is_dir():
        if expected_sha256:
            result.warnings.append("expected SHA-256 is only checked for ZIP packages")
        folder = package
    elif package.is_file() and zipfile.is_zipfile(package):
        size = package.stat().st_size
        if size > max_size_bytes:
            result.errors.append(f"package is larger than {max_size_bytes} bytes")
            return result
        if expected_sha256 is not None:
            actual = sha256_file(package).lower()
            if actual != str(expected_sha256).strip().lower():
                result.errors.append(
                    f"SHA-256 mismatch: expected {expected_sha256}, got {actual}"
                )
        try:
            with zipfile.ZipFile(package) as archive:
                for member in archive.infolist():
                    name = member.filename.replace("\\", "/")
                    if not name or name.endswith("/"):
                        continue
                    parts = Path(name).parts
                    if name.startswith("/") or ".." in parts:
                        result.errors.append(f"unsafe archive entry: {member.filename}")
                if result.errors:
                    return result
                uncompressed = sum(member.file_size for member in archive.infolist())
                if uncompressed > max_size_bytes:
                    result.errors.append("uncompressed package is too large")
                    return result
        except (zipfile.BadZipFile, OSError) as exc:
            result.errors.append(f"invalid ZIP archive: {exc}")
            return result

        with tempfile.TemporaryDirectory(prefix="workmods_validate_package_") as tmp:
            try:
                folder = safe_extract(package, Path(tmp) / "extracted")
            except StorageError as exc:
                result.errors.append(str(exc))
                return result
            folder_result = validate_mod(folder, compatibility=compatibility)
            result.errors.extend(folder_result.errors)
            result.warnings.extend(folder_result.warnings)
            return result

    else:
        result.errors.append(f"not a mod folder or ZIP archive: {package}")
        return result

    folder_result = validate_mod(folder, compatibility=compatibility)
    result.errors.extend(folder_result.errors)
    result.warnings.extend(folder_result.warnings)
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


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _version_key(value: Any) -> tuple[int, ...]:
    text = str(value or "").strip().lower().lstrip("v")
    numbers = [int(part) for part in re.findall(r"\d+", text)]
    return tuple(numbers) if numbers else (0,)


def _compatibility_target(compatibility: Any) -> dict[str, Any]:
    if compatibility is None:
        return {}
    if isinstance(compatibility, dict):
        return dict(compatibility)
    if isinstance(compatibility, str):
        text = compatibility.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"platforms": parsed}
        except (json.JSONDecodeError, ValueError):
            pass
        result: dict[str, Any] = {}
        for chunk in text.replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" in chunk:
                key, value = chunk.split(":", 1)
                result[key.strip()] = value.strip()
            else:
                result.setdefault("platforms", []).append(chunk)
        return result
    if isinstance(compatibility, (list, tuple, set)):
        return {"platforms": list(compatibility)}
    if hasattr(compatibility, "to_dict"):
        try:
            return dict(compatibility.to_dict())
        except Exception:
            pass
    return {"target": str(compatibility)}


def _manifest_compatibility(manifest: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    compat = manifest.get("compatibility")
    if isinstance(compat, dict):
        result.update(compat)
    for key in (
        "engine", "sdk", "unity", "unity_version", "min_unity_version", "max_unity_version",
        "min_unity", "max_unity", "target_unity_version", "platforms", "supported_platforms",
        "target_platforms", "client_version", "min_client_version", "requires_client",
        "sdk_version", "min_sdk_version", "requires_sdk", "min_client", "min_sdk",
    ):
        if key in manifest and manifest.get(key) is not None:
            result.setdefault(key, manifest.get(key))
    return result


def _validate_compatibility(
    result: ValidationResult, manifest: dict[str, Any], compatibility: Any
) -> None:
    target = _compatibility_target(compatibility)
    if not target:
        return
    manifest_compat = _manifest_compatibility(manifest)

    target_engine = (
        target.get("engine") or target.get("sdk") or target.get("target_engine")
        or target.get("target_sdk")
    )
    manifest_engine = (
        manifest_compat.get("engine") or manifest_compat.get("sdk")
        or manifest_compat.get("target_engine")
    )
    if target_engine:
        if manifest_engine:
            if str(target_engine).strip().lower() != str(manifest_engine).strip().lower():
                result.errors.append(
                    f"incompatible engine: manifest targets {manifest_engine}, requested {target_engine}"
                )
        else:
            result.warnings.append("manifest does not declare an engine/sdk; compatibility cannot be verified")

    target_unity = (
        target.get("unity_version") or target.get("unity") or target.get("target_unity_version")
        or target.get("target_unity")
    )
    manifest_min_unity = (
        manifest_compat.get("min_unity_version") or manifest_compat.get("min_unity")
        or manifest_compat.get("minimum_unity_version")
    )
    manifest_max_unity = (
        manifest_compat.get("max_unity_version") or manifest_compat.get("max_unity")
        or manifest_compat.get("maximum_unity_version")
    )
    manifest_unity = (
        manifest_compat.get("unity_version") or manifest_compat.get("unity")
        or manifest_compat.get("target_unity_version")
    )
    if target_unity:
        if manifest_min_unity and _version_key(target_unity) < _version_key(manifest_min_unity):
            result.errors.append(
                f"incompatible Unity version: requires at least {manifest_min_unity}, got {target_unity}"
            )
        if manifest_max_unity and _version_key(target_unity) > _version_key(manifest_max_unity):
            result.errors.append(
                f"incompatible Unity version: supports up to {manifest_max_unity}, got {target_unity}"
            )
        if manifest_unity:
            if _version_key(target_unity) < _version_key(manifest_unity):
                result.errors.append(
                    f"incompatible Unity version: requires at least {manifest_unity}, got {target_unity}"
                )
        if not (manifest_min_unity or manifest_max_unity or manifest_unity):
            result.warnings.append("manifest does not declare a Unity version; compatibility cannot be verified")

    target_platforms = _as_list(
        target.get("platforms") or target.get("platform") or target.get("target_platforms")
        or target.get("target_platform")
    )
    manifest_platforms = _as_list(
        manifest_compat.get("platforms") or manifest_compat.get("supported_platforms")
        or manifest_compat.get("target_platforms")
    )
    if target_platforms:
        if manifest_platforms:
            if not (set(p.lower() for p in manifest_platforms) & set(p.lower() for p in target_platforms)):
                result.errors.append(
                    f"incompatible platform: manifest supports {manifest_platforms}, requested {target_platforms}"
                )
        else:
            result.warnings.append("manifest does not declare supported platforms; compatibility cannot be verified")

    min_client = (
        manifest_compat.get("min_client_version") or manifest_compat.get("requires_client")
        or manifest_compat.get("min_client")
    )
    target_client = target.get("client_version") or target.get("target_client_version") or APP_VERSION
    if min_client:
        if _version_key(target_client) < _version_key(min_client):
            result.errors.append(
                f"incompatible client version: requires at least {min_client}, got {target_client}"
            )

    min_sdk = (
        manifest_compat.get("min_sdk_version") or manifest_compat.get("requires_sdk")
        or manifest_compat.get("min_sdk")
    )
    target_sdk = target.get("sdk_version") or target.get("target_sdk_version") or target.get("unity_sdk_version")
    if min_sdk:
        if target_sdk and _version_key(target_sdk) < _version_key(min_sdk):
            result.errors.append(
                f"incompatible SDK version: requires at least {min_sdk}, got {target_sdk}"
            )
        elif not target_sdk:
            result.warnings.append("target SDK version was not provided; SDK compatibility cannot be verified")


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
    "validate_package",
    "version_problem",
]
