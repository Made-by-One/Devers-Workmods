"""Application settings, paths and credentials.

Configuration is a single JSON file (``~/.devers_workmods/config.json`` by
default) that keeps one *game profile* per target game. Every profile carries
its own install directory, which is what makes one Workmods installation able to
manage mods for several unrelated Unity games.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from workmods.models import DEFAULT_GAME_ID, UNASSIGNED_GAME_NAME, Game, normalize_game_id

APP_NAME = "Workmods"
APP_VERSION = "1.1d"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("WORKMODS_DATA_DIR", PROJECT_ROOT / "data"))

CONFIG_DIR = Path(os.environ.get("WORKMODS_CONFIG_DIR", Path.home() / ".devers_workmods"))
CONFIG_FILE = CONFIG_DIR / "config.json"

# --- Registry / GitHub endpoints -------------------------------------------
# The registry repository is the single source of truth shared by every client.
REGISTRY_REPO = os.environ.get("WORKMODS_REGISTRY_REPO", "Made-by-One/Devers-Workmods")
REGISTRY_BRANCH = os.environ.get("WORKMODS_REGISTRY_BRANCH", "main")
DEFAULT_REGISTRY_URL = (
    f"https://raw.githubusercontent.com/{REGISTRY_REPO}/{REGISTRY_BRANCH}/registry.json"
)

# --- OAuth application ------------------------------------------------------
# A desktop OAuth app cannot keep a client secret truly confidential. These
# values are only defaults so existing installs keep working; deployments should
# override them through the environment.
GITHUB_CLIENT_ID = os.environ.get("WORKMODS_GITHUB_CLIENT_ID", "Ov23liTU4bp8UkRw1Wco")
GITHUB_CLIENT_SECRET = os.environ.get(
    "WORKMODS_GITHUB_CLIENT_SECRET", "876493fead76f7880f20e51c7dc072832e4980e2"
)
OAUTH_CALLBACK_PORT = int(os.environ.get("WORKMODS_OAUTH_PORT", "8080"))
OAUTH_SCOPE = "repo"


def default_mods_dir(game_id: str = DEFAULT_GAME_ID) -> str:
    """Default install directory for a game profile."""
    base = Path.home() / "DeversMods"
    game_id = normalize_game_id(game_id)
    return str(base if game_id == DEFAULT_GAME_ID else base / game_id)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class WorkmodsConfig:
    """User configuration with one install directory per game."""

    registry_url: str = DEFAULT_REGISTRY_URL
    # Empty means "not chosen yet": the UI falls back to the system language.
    language: str = ""
    github_token: str = ""
    active_game_id: str = DEFAULT_GAME_ID
    games: list[Game] = field(
        default_factory=lambda: [
            Game(DEFAULT_GAME_ID, UNASSIGNED_GAME_NAME, default_mods_dir(DEFAULT_GAME_ID))
        ]
    )

    # -- game profiles ------------------------------------------------------
    def game(self, game_id: str | None) -> Game | None:
        game_id = normalize_game_id(game_id)
        for game in self.games:
            if game.id == game_id:
                return game
        return None

    def game_name(self, game_id: str | None) -> str:
        game = self.game(game_id)
        return game.display_name if game else normalize_game_id(game_id)

    def ensure_game(self, game_id: str, name: str = "") -> Game:
        """Return the profile for ``game_id``, creating it when missing."""
        game_id = normalize_game_id(game_id)
        existing = self.game(game_id)
        if existing:
            if name and existing.name in (existing.id, UNASSIGNED_GAME_NAME):
                existing.name = name
            return existing
        game = Game(game_id, name or game_id, default_mods_dir(game_id))
        self.games.append(game)
        return game

    def add_game(self, game: Game) -> Game:
        existing = self.game(game.id)
        if existing:
            existing.name = game.name or existing.name
            existing.install_dir = game.install_dir or existing.install_dir
            existing.sdk = game.sdk or existing.sdk
            return existing
        if not game.install_dir:
            game.install_dir = default_mods_dir(game.id)
        self.games.append(game)
        return game

    def remove_game(self, game_id: str) -> bool:
        """Remove a profile. The default profile is always kept."""
        game_id = normalize_game_id(game_id)
        if game_id == DEFAULT_GAME_ID:
            return False
        before = len(self.games)
        self.games = [g for g in self.games if g.id != game_id]
        if self.active_game_id == game_id:
            self.active_game_id = DEFAULT_GAME_ID
        return len(self.games) != before

    def install_dir_for(self, game_id: str | None = None) -> Path:
        game_id = normalize_game_id(game_id or self.active_game_id)
        game = self.game(game_id)
        if game and game.install_dir:
            return Path(game.install_dir).expanduser()
        return Path(default_mods_dir(game_id))

    @property
    def install_dir(self) -> Path:
        """Install directory of the currently selected game."""
        return self.install_dir_for(self.active_game_id)

    def iter_game_dirs(self) -> Iterator[tuple[Game, Path]]:
        """Yield every configured game with a resolved install directory."""
        seen: set[str] = set()
        for game in self.games:
            if game.id in seen:
                continue
            seen.add(game.id)
            yield game, self.install_dir_for(game.id)

    @property
    def active_game(self) -> Game:
        return self.game(self.active_game_id) or self.ensure_game(self.active_game_id)

    # -- persistence --------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkmodsConfig":
        """Build a config, migrating the pre-1.0 flat layout.

        Old configs only had ``install_dir``. That directory becomes the default
        game's install directory so existing users keep their mods.
        """
        data = dict(data or {})
        raw_games = data.get("games")
        games: list[Game] = []
        if isinstance(raw_games, list):
            for entry in raw_games:
                if isinstance(entry, dict):
                    games.append(Game.from_dict(entry))
        if not games:
            legacy_dir = str(data.get("install_dir") or "").strip()
            games = [
                Game(
                    DEFAULT_GAME_ID,
                    UNASSIGNED_GAME_NAME,
                    legacy_dir or default_mods_dir(DEFAULT_GAME_ID),
                )
            ]

        cfg = cls(
            registry_url=str(data.get("registry_url") or DEFAULT_REGISTRY_URL),
            language=str(data.get("language") or ""),
            github_token=str(data.get("github_token") or ""),
            active_game_id=normalize_game_id(data.get("active_game_id")),
            games=games,
        )
        if not cfg.game(cfg.active_game_id):
            cfg.active_game_id = DEFAULT_GAME_ID
        cfg.ensure_game(DEFAULT_GAME_ID)
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_url": self.registry_url,
            "language": self.language,
            "github_token": self.github_token,
            "active_game_id": self.active_game_id,
            "games": [game.to_dict() for game in self.games],
        }

    @classmethod
    def load(cls, path: Path | None = None) -> "WorkmodsConfig":
        path = Path(path or CONFIG_FILE)
        if not path.exists():
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return cls.from_dict(json.load(handle))
        except (OSError, ValueError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        path = Path(path or CONFIG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)


__all__ = [
    "APP_NAME", "APP_VERSION", "CONFIG_DIR", "CONFIG_FILE",
    "DATA_DIR", "DEFAULT_REGISTRY_URL", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET",
    "OAUTH_CALLBACK_PORT", "OAUTH_SCOPE", "PROJECT_ROOT", "REGISTRY_BRANCH",
    "REGISTRY_REPO", "WorkmodsConfig", "default_mods_dir",
]
