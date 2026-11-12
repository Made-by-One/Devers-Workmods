"""Client self-update helpers.

The updater talks to the GitHub Releases API, downloads an asset, verifies it and
replaces the running executable. Verification is deliberately layered: a SHA-256
digest is always checked when one is available, and an optional detached
signature is checked when a public key is configured. If applying an update
fails, the previous executable is restored from a backup.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from workmods.config import APP_NAME, APP_VERSION

GITHUB_API = "https://api.github.com"


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, verified or applied."""


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    content_type: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "size": self.size,
            "content_type": self.content_type,
            "sha256": self.sha256,
        }


@dataclass
class ReleaseInfo:
    tag_name: str
    version: str
    name: str = ""
    body: str = ""
    published_at: str = ""
    html_url: str = ""
    assets: list[ReleaseAsset] = field(default_factory=list)

    def asset(self, name: str | None = None) -> ReleaseAsset | None:
        if name:
            for item in self.assets:
                if item.name == name:
                    return item
            return None
        for item in self.assets:
            if item.name.endswith((".exe", ".zip", ".tar.gz", ".dmg", ".app")):
                return item
        return self.assets[0] if self.assets else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag_name": self.tag_name,
            "version": self.version,
            "name": self.name,
            "body": self.body,
            "published_at": self.published_at,
            "html_url": self.html_url,
            "assets": [item.to_dict() for item in self.assets],
        }


@dataclass
class UpdateResult:
    source: Path
    target: Path
    backup: Path | None
    version: str
    applied: bool
    rolled_back: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "target": str(self.target),
            "backup": str(self.backup) if self.backup else "",
            "version": self.version,
            "applied": self.applied,
            "rolled_back": self.rolled_back,
            "message": self.message,
        }


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _version_key(value: Any) -> tuple[int, ...]:
    text = str(value or "").strip().lower().lstrip("v")
    numbers = [int(part) for part in __import__("re").findall(r"\d+", text)]
    return tuple(numbers) if numbers else (0,)


def is_newer(candidate: Any, current: Any = APP_VERSION) -> bool:
    return _version_key(candidate) > _version_key(current)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sha256(path: str | Path, expected: str) -> bool:
    path = Path(path)
    if not expected:
        return True
    return _sha256_file(path).lower() == str(expected).strip().lower()


def _signature_bytes(signature: str | Path | bytes) -> bytes:
    if isinstance(signature, (str, Path)):
        sig_path = Path(signature)
        if sig_path.exists():
            return sig_path.read_bytes()
        try:
            return bytes.fromhex(str(signature))
        except ValueError:
            return str(signature).encode()
    return bytes(signature)


def verify_signature_data(
    data: bytes,
    signature: str | Path | bytes,
    *,
    public_key: str | Path | bytes | None = None,
    algorithm: str = "sha256",
) -> bool:
    """Verify a detached signature over ``data`` when a public key is available.

    This uses the optional ``cryptography`` package. If it is not installed, or no
    key is provided, verification returns ``False`` instead of pretending to work.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    except Exception:
        return False

    if not public_key:
        return False

    try:
        if isinstance(public_key, bytes):
            key_data = public_key
        elif isinstance(public_key, (str, Path)) and Path(public_key).exists():
            key_data = Path(public_key).read_bytes()
        else:
            key_data = str(public_key).encode()
        key = serialization.load_pem_public_key(key_data)
    except Exception:
        return False

    signature_bytes = _signature_bytes(signature)
    hash_algorithm = hashes.SHA256() if algorithm.lower() in {"sha256", "sha-256"} else hashes.SHA256()
    try:
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(signature_bytes, data, padding.PKCS1v15(), hash_algorithm)
            return True
        if isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(signature_bytes, data, ec.ECDSA(hash_algorithm))
            return True
    except Exception:
        return False
    return False


def verify_signature(
    path: str | Path,
    signature: str | Path | bytes,
    *,
    public_key: str | Path | bytes | None = None,
    algorithm: str = "sha256",
) -> bool:
    """Verify a detached signature for a file."""
    return verify_signature_data(
        Path(path).read_bytes(), signature, public_key=public_key, algorithm=algorithm
    )


class GitHubReleaseClient:
    def __init__(
        self,
        repo: str = "Made-by-One/Devers-Workmods",
        token: str = "",
        api_base: str = GITHUB_API,
        timeout: int = 30,
    ):
        self.repo = repo.strip().strip("/")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": APP_NAME}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def latest_release(self) -> ReleaseInfo:
        url = f"{self.api_base}/repos/{self.repo}/releases/latest"
        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise UpdateError(f"cannot fetch latest release: {exc}") from exc
        return self._parse_release(payload)

    def release_by_tag(self, tag: str) -> ReleaseInfo:
        url = f"{self.api_base}/repos/{self.repo}/releases/tags/{tag}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise UpdateError(f"cannot fetch release {tag}: {exc}") from exc
        return self._parse_release(payload)

    def _parse_release(self, payload: dict[str, Any]) -> ReleaseInfo:
        assets = []
        for item in payload.get("assets") or []:
            assets.append(
                ReleaseAsset(
                    name=str(item.get("name") or ""),
                    url=str(item.get("browser_download_url") or item.get("url") or ""),
                    size=int(item.get("size") or 0),
                    content_type=str(item.get("content_type") or ""),
                )
            )
        tag = str(payload.get("tag_name") or "")
        version = tag.lstrip("v") if tag.lower().startswith("v") else tag
        return ReleaseInfo(
            tag_name=tag,
            version=version,
            name=str(payload.get("name") or ""),
            body=str(payload.get("body") or ""),
            published_at=str(payload.get("published_at") or ""),
            html_url=str(payload.get("html_url") or ""),
            assets=assets,
        )


class ClientUpdater:
    """High-level update workflow for the desktop client."""

    def __init__(
        self,
        *,
        current_version: str = APP_VERSION,
        repo: str = "Made-by-One/Devers-Workmods",
        token: str = "",
        executable_path: str | Path | None = None,
        state_dir: str | Path | None = None,
        backup_dir: str | Path | None = None,
        public_key: str | Path | None = None,
    ):
        self.current_version = current_version
        self.public_key = public_key or os.environ.get("WORKMODS_RELEASE_PUBLIC_KEY", "") or None
        self.repo = repo
        self.token = token
        self.release_client = GitHubReleaseClient(repo=repo, token=token)
        self.executable_path = Path(executable_path or sys.executable).resolve()
        self.state_dir = Path(state_dir or Path.home() / ".devers_workmods")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path(backup_dir or self.state_dir / "updates")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "update_state.json"

    # -- checks -------------------------------------------------------------
    def check_for_updates(self) -> ReleaseInfo | None:
        release = self.release_client.latest_release()
        if is_newer(release.version, self.current_version):
            return release
        return None

    @staticmethod
    def platform_asset_name() -> str:
        if sys.platform.startswith("win"):
            return "Workmods-windows-x86_64.zip"
        if sys.platform == "darwin":
            return "Workmods-macos.zip"
        return "Workmods-linux-x86_64.tar.gz"

    def select_asset(self, release: ReleaseInfo, asset_name: str | None = None) -> ReleaseAsset | None:
        return release.asset(asset_name or self.platform_asset_name()) or release.asset()

    def _asset_bytes(self, asset: ReleaseAsset | None) -> bytes:
        if asset is None or not asset.url:
            return b""
        try:
            response = requests.get(asset.url, timeout=60, allow_redirects=True)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            raise UpdateError(f"cannot fetch {asset.name}: {exc}") from exc

    def checksum_for_asset(
        self,
        release: ReleaseInfo,
        asset_name: str,
        *,
        checksums_name: str = "SHA256SUMS",
    ) -> str:
        """Return the published SHA-256 for ``asset_name``, or an empty string."""
        checksums = release.asset(checksums_name) or release.asset("checksums.txt")
        if checksums is None:
            return ""
        text = self._asset_bytes(checksums).decode("utf-8", errors="replace")
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1].lstrip("*") == asset_name:
                return parts[0].lower()
        return ""

    def signature_for_checksums(self, release: ReleaseInfo) -> bytes | None:
        for name in ("SHA256SUMS.sig", "SHA256SUMS.asc", "checksums.txt.sig"):
            asset = release.asset(name)
            if asset is not None:
                return self._asset_bytes(asset)
        return None

    def download_release(
        self,
        release: ReleaseInfo,
        *,
        asset_name: str | None = None,
        destination: str | Path | None = None,
        progress: Callable[[int, int], None] | None = None,
        timeout: int = 300,
    ) -> Path:
        asset = self.select_asset(release, asset_name)
        if asset is None or not asset.url:
            raise UpdateError("release has no downloadable asset")
        dest = Path(destination) if destination else self.backup_dir / asset.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with requests.get(asset.url, stream=True, timeout=timeout, allow_redirects=True) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or asset.size or 0)
                done = 0
                with open(dest, "wb") as handle:
                    for chunk in response.iter_content(64 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
        except Exception as exc:
            raise UpdateError(f"cannot download release: {exc}") from exc
        return dest

    def verify_download(
        self,
        path: str | Path,
        *,
        expected_sha256: str = "",
        signature: str | Path | bytes | None = None,
        require_signature: bool = False,
    ) -> None:
        path = Path(path)
        if expected_sha256 and not verify_sha256(path, expected_sha256):
            raise UpdateError("SHA-256 verification failed")
        if require_signature:
            if not self.public_key:
                raise UpdateError("no public key configured for signature verification")
            if signature is None:
                raise UpdateError("release signature is missing")
            if not verify_signature(path, signature, public_key=self.public_key):
                raise UpdateError("release signature verification failed")
        elif signature is not None and self.public_key:
            # Best effort: do not fail the update if a signature is present but
            # optional verification cannot be performed.
            verify_signature(path, signature, public_key=self.public_key)

    def verify_release_asset(
        self,
        release: ReleaseInfo,
        path: str | Path,
        *,
        asset_name: str = "",
        require_signature: bool = False,
    ) -> str:
        """Verify an asset against ``SHA256SUMS`` and an optional signature."""
        path = Path(path)
        name = asset_name or path.name
        checksum = self.checksum_for_asset(release, name)
        if checksum:
            self.verify_download(path, expected_sha256=checksum)
        signature = self.signature_for_checksums(release)
        checksums = release.asset("SHA256SUMS") or release.asset("checksums.txt")
        if signature is not None and checksums is not None:
            checksums_data = self._asset_bytes(checksums)
            if self.public_key:
                if not verify_signature_data(
                    checksums_data, signature, public_key=self.public_key
                ):
                    raise UpdateError("release checksum signature verification failed")
            elif require_signature:
                raise UpdateError("no public key configured for signature verification")
        elif require_signature:
            raise UpdateError("signed checksums are missing from this release")
        return checksum

    # -- apply / rollback ---------------------------------------------------
    def _state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _clear_state(self) -> None:
        try:
            self.state_file.unlink()
        except FileNotFoundError:
            pass

    def _prepare_update_executable(self, update_path: Path) -> Path:
        """Return the executable inside a release archive, or the file itself."""
        name = update_path.name.lower()
        if not name.endswith((".zip", ".tar.gz", ".tgz")):
            return update_path
        extract_dir = self.backup_dir / "extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        if name.endswith(".zip"):
            with zipfile.ZipFile(update_path) as archive:
                for member in archive.infolist():
                    member_name = member.filename.replace("\\", "/")
                    if member_name.startswith("/") or ".." in Path(member_name).parts:
                        raise UpdateError(f"unsafe update archive entry: {member.filename}")
                archive.extractall(extract_dir)
        else:
            with tarfile.open(update_path, "r:gz") as archive:
                for member in archive.getmembers():
                    if member.name.startswith("/") or ".." in Path(member.name).parts:
                        raise UpdateError(f"unsafe update archive entry: {member.name}")
                archive.extractall(extract_dir, filter="data")
        candidates = [
            path for path in extract_dir.rglob("*")
            if path.is_file() and path.name in {"Workmods", "Workmods.exe"}
        ]
        if not candidates:
            raise UpdateError("update archive does not contain a Workmods executable")
        return candidates[0]

    def apply_update(
        self,
        update_path: str | Path,
        *,
        target: str | Path | None = None,
        version: str = "",
        backup: bool = True,
        rollback_on_failure: bool = True,
    ) -> UpdateResult:
        update_path = self._prepare_update_executable(Path(update_path))
        target = Path(target or self.executable_path)
        backup_path = self.backup_dir / f"{target.name}.previous" if backup else None
        result = UpdateResult(source=update_path, target=target, backup=backup_path, version=version, applied=False)

        if not update_path.is_file():
            raise UpdateError(f"update file does not exist: {update_path}")

        try:
            if backup and target.exists():
                if backup_path and backup_path.exists():
                    backup_path.unlink()
                target.replace(backup_path)
            if target.parent and not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(update_path, target)
            try:
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
            result.applied = True
            self._write_state(
                {
                    "pending": True,
                    "target": str(target),
                    "backup": str(backup_path) if backup_path else "",
                    "version": version,
                    "applied_at": _now(),
                }
            )
            result.message = "update applied"
            return result
        except Exception as exc:
            result.message = str(exc)
            if rollback_on_failure and backup_path and backup_path.exists():
                try:
                    if target.exists():
                        target.unlink()
                    backup_path.replace(target)
                    result.rolled_back = True
                    result.message = f"update failed and was rolled back: {exc}"
                except Exception as rollback_exc:
                    result.message = f"update failed ({exc}); rollback failed ({rollback_exc})"
            self._clear_state()
            raise UpdateError(result.message) from exc

    def rollback(self, *, target: str | Path | None = None) -> bool:
        state = self._state()
        backup_value = state.get("backup") or ""
        backup_path = Path(backup_value) if backup_value else None
        target_path = Path(target or state.get("target") or self.executable_path)
        if backup_path is None:
            backup_path = self.backup_dir / f"{target_path.name}.previous"
        if not backup_path or not backup_path.exists():
            return False
        try:
            if target_path.exists():
                target_path.unlink()
            backup_path.replace(target_path)
            self._clear_state()
            return True
        except OSError:
            return False

    def finalize_pending_update(self) -> bool:
        state = self._state()
        if not state.get("pending"):
            return False
        backup_value = state.get("backup") or ""
        backup_path = Path(backup_value) if backup_value else None
        # Keep the backup for one successful launch, then remove it.
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass
        self._clear_state()
        return True

    def cleanup(self) -> None:
        for path in self.backup_dir.glob("*.previous"):
            try:
                path.unlink()
            except OSError:
                pass


__all__ = [
    "APP_NAME",
    "ClientUpdater",
    "GitHubReleaseClient",
    "ReleaseAsset",
    "ReleaseInfo",
    "UpdateError",
    "UpdateResult",
    "is_newer",
    "verify_sha256",
    "verify_signature",
    "verify_signature_data",
]
