"""Parsing and querying the shared mod registry.

The registry is a plain JSON document served from GitHub. Version 2 adds the
``games`` catalogue and a mandatory ``game_id`` on every mod; version 1
documents (``{"mods": [...]}``) are migrated on read so old clients, old
registries and old payloads keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from workmods.models import DEFAULT_GAME_ID, Game, Mod, normalize_game_id

SCHEMA_VERSION = 2
ALL_GAMES = ""  # sentinel used by UI filters for "no game filter"


@dataclass
class Registry:
    schema_version: int = SCHEMA_VERSION
    games: list[Game] = field(default_factory=list)
    mods: list[Mod] = field(default_factory=list)
    updated_at: str = ""

    @classmethod
    def from_payload(cls, payload: Any) -> "Registry":
        if isinstance(payload, list):  # tolerate a bare list of mods
            payload = {"mods": payload}
        if not isinstance(payload, dict):
            raise ValueError("Registry payload must be a JSON object")

        raw_games = payload.get("games") or []
        games: list[Game] = []
        if isinstance(raw_games, list):
            for entry in raw_games:
                if isinstance(entry, dict) and entry.get("id"):
                    games.append(Game.from_dict(entry))

        raw_mods = payload.get("mods") or []
        mods: list[Mod] = []
        if isinstance(raw_mods, list):
            for entry in raw_mods:
                if isinstance(entry, dict) and entry.get("id"):
                    mods.append(Mod.from_dict(entry))

        # Every game referenced by a mod must have a profile to be selectable.
        known = {g.id for g in games}
        for mod in mods:
            if mod.game_id not in known:
                known.add(mod.game_id)
                games.append(Game(mod.game_id))

        try:
            schema = int(payload.get("schema_version") or 1)
        except (TypeError, ValueError):
            schema = 1

        return cls(
            schema_version=max(schema, 1),
            games=games,
            mods=mods,
            updated_at=str(payload.get("updated_at") or ""),
        )

    @property
    def game_ids(self) -> list[str]:
        return [game.id for game in self.games]

    def game_name(self, game_id: str | None) -> str:
        target = normalize_game_id(game_id)
        for game in self.games:
            if game.id == target:
                return game.display_name
        return target

    def filter(
        self,
        game_id: str | None = None,
        query: str = "",
        *,
        include_unassigned: bool = False,
    ) -> list[Mod]:
        """Return mods for one game, optionally narrowed by a search query."""
        return [
            mod
            for mod in self.mods
            if mod_matches(mod, game_id, query, include_unassigned=include_unassigned)
        ]

    def mods_by_id(self) -> dict[str, Mod]:
        return {mod.id: mod for mod in self.mods}


def mod_matches(
    mod: Mod,
    game_id: str | None = None,
    query: str = "",
    *,
    include_unassigned: bool = False,
) -> bool:
    """Single source of truth for catalog filtering.

    ``game_id`` of ``None``/``""`` means "every game". ``include_unassigned``
    keeps legacy mods visible while a specific game is selected, which is handy
    for single-game registries that predate ``game_id``.
    """
    target = normalize_game_id(game_id) if game_id else ALL_GAMES
    if target != ALL_GAMES and mod.game_id != target:
        if not (include_unassigned and mod.game_id == DEFAULT_GAME_ID):
            return False

    needle = (query or "").strip().lower()
    if not needle:
        return True

    haystack = " ".join(
        [
            mod.name,
            mod.id,
            mod.author,
            mod.description,
            mod.game_id,
            mod.version,
            mod.entry_asset,
            " ".join(mod.tags),
        ]
    ).lower()
    return all(term in haystack for term in needle.split())


def merge_games(configured: Iterable[Game], registry_games: Iterable[Game]) -> list[Game]:
    """Combine local game profiles with registry games, local values winning."""
    merged: dict[str, Game] = {}
    for game in registry_games:
        merged[game.id] = game
    for game in configured:
        local = merged.get(game.id)
        if local is None:
            merged[game.id] = game
        else:
            local.name = game.name or local.name
            local.install_dir = game.install_dir or local.install_dir
            local.sdk = game.sdk or local.sdk
    return sorted(merged.values(), key=lambda g: (g.id != DEFAULT_GAME_ID, g.name.lower()))


__all__ = ["ALL_GAMES", "SCHEMA_VERSION", "Registry", "merge_games", "mod_matches"]
