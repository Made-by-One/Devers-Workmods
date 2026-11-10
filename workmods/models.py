"""Plain data objects shared by every layer.

These types intentionally depend on nothing but the standard library: the UI may
import them, but they never import the UI, Qt or network code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_GAME_ID = "default"
UNASSIGNED_GAME_NAME = "Unassigned"


def normalize_game_id(value: Any) -> str:
    """Return a safe, lower-case game id; empty values become ``default``.

    Game ids end up in folder names, registry payloads and SDK lookups, so they
    are restricted to a conservative character set.
    """
    game_id = str(value or "").strip().lower()
    if not game_id:
        return DEFAULT_GAME_ID
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in game_id)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or DEFAULT_GAME_ID


@dataclass
class Game:
    """A target game (for example ``space-rangers``) and where its mods live."""

    id: str
    name: str = ""
    install_dir: str = ""
    sdk: str = "unity"

    def __post_init__(self) -> None:
        self.id = normalize_game_id(self.id)
        self.name = str(self.name or "").strip() or (
            UNASSIGNED_GAME_NAME if self.id == DEFAULT_GAME_ID else self.id
        )
        self.install_dir = str(self.install_dir or "").strip()
        self.sdk = str(self.sdk or "unity").strip() or "unity"

    @property
    def display_name(self) -> str:
        return self.name if self.name == self.id else f"{self.name} ({self.id})"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Game":
        data = data or {}
        return cls(
            id=data.get("id", DEFAULT_GAME_ID),
            name=data.get("name", ""),
            install_dir=data.get("install_dir", ""),
            sdk=data.get("sdk", "unity"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "install_dir": self.install_dir,
            "sdk": self.sdk,
        }


@dataclass
class Mod:
    """A mod as described by ``registry.json`` (or a local draft)."""

    id: str
    game_id: str = DEFAULT_GAME_ID
    name: str = ""
    version: str = ""
    author: str = ""
    description: str = ""
    repo: str = ""
    download_url: str = ""
    sha256: str = ""
    icon_url: str = ""
    banner_url: str = ""
    updated_at: str = ""
    entry_asset: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = str(self.id or "").strip()
        self.game_id = normalize_game_id(self.game_id)
        self.name = str(self.name or "").strip() or self.id
        self.version = str(self.version or "").strip()
        self.author = str(self.author or "").strip()
        self.description = str(self.description or "").strip()
        self.repo = str(self.repo or "").strip()
        self.download_url = str(self.download_url or "").strip()
        self.sha256 = str(self.sha256 or "").strip().lower()
        self.icon_url = str(self.icon_url or "").strip()
        self.banner_url = str(self.banner_url or "").strip()
        self.updated_at = str(self.updated_at or "").strip()
        self.entry_asset = str(self.entry_asset or "").strip()
        if isinstance(self.tags, str):
            self.tags = [t.strip() for t in self.tags.split(",") if t.strip()]
        else:
            self.tags = [str(t).strip() for t in (self.tags or []) if str(t).strip()]

    @property
    def version_label(self) -> str:
        return f"v{self.version}" if self.version else "v?"

    @property
    def is_installable(self) -> bool:
        return bool(self.download_url)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Mod":
        data = dict(data or {})
        known = {
            "id", "game_id", "name", "version", "author", "description", "repo",
            "download_url", "sha256", "icon_url", "banner_url", "updated_at",
            "entry_asset", "tags",
        }
        kwargs = {k: v for k, v in data.items() if k in known and v is not None}
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "game_id": self.game_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "repo": self.repo,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "icon_url": self.icon_url,
            "banner_url": self.banner_url,
            "updated_at": self.updated_at,
            "entry_asset": self.entry_asset,
            "tags": list(self.tags),
        }


@dataclass
class InstalledMod:
    """A folder on disk under a game's install directory."""

    mod_id: str
    path: str
    game_id: str = DEFAULT_GAME_ID
    name: str = ""
    version: str = ""
    author: str = ""
    description: str = ""
    entry_asset: str = ""
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or self.mod_id

    @property
    def version_label(self) -> str:
        return f"v{self.version}" if self.version else "v?"

    def to_mod(self) -> Mod:
        """Best-effort conversion for display in catalog-style lists."""
        return Mod(
            id=self.mod_id,
            game_id=self.game_id,
            name=self.name or self.mod_id,
            version=self.version,
            author=self.author,
            description=self.description,
            entry_asset=self.entry_asset,
        )
