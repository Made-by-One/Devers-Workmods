"""Mod profiles: named enabled/disabled sets, settings presets and import/export.

A profile is a small JSON document that records which mods are enabled for a game
and the settings preset that goes with them. Profiles are intentionally separate
from ``WorkmodsConfig`` so they can be shared between players and machines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from workmods.models import DEFAULT_GAME_ID, normalize_game_id


class ProfileError(RuntimeError):
    """Raised when a profile cannot be created, loaded or imported."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


@dataclass
class ModProfile:
    """A named set of enabled mods and settings for one game."""

    name: str
    game_id: str = DEFAULT_GAME_ID
    enabled: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_preset: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.name = str(self.name or "").strip()
        if not self.name:
            raise ProfileError("profile name is required")
        self.game_id = normalize_game_id(self.game_id)
        self.enabled = _as_list(self.enabled)
        self.disabled = _as_list(self.disabled)
        if not isinstance(self.settings, dict):
            self.settings = {}
        if not isinstance(self.presets, dict):
            self.presets = {}
        self.active_preset = str(self.active_preset or "").strip()
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = self.created_at

    def enable(self, mod_id: str) -> None:
        mod_id = str(mod_id).strip()
        if not mod_id:
            return
        if mod_id not in self.enabled:
            self.enabled.append(mod_id)
        self.disabled = [item for item in self.disabled if item != mod_id]
        self.updated_at = _now()

    def disable(self, mod_id: str) -> None:
        mod_id = str(mod_id).strip()
        if not mod_id:
            return
        if mod_id not in self.disabled:
            self.disabled.append(mod_id)
        self.enabled = [item for item in self.enabled if item != mod_id]
        self.updated_at = _now()

    def toggle(self, mod_id: str, enabled: bool | None = None) -> bool:
        mod_id = str(mod_id).strip()
        if enabled is None:
            enabled = mod_id not in self.enabled
        if enabled:
            self.enable(mod_id)
        else:
            self.disable(mod_id)
        return enabled

    def is_enabled(self, mod_id: str) -> bool:
        return str(mod_id).strip() in self.enabled

    def save_preset(self, name: str, settings: dict[str, Any] | None = None) -> None:
        name = str(name or "").strip()
        if not name:
            raise ProfileError("preset name is required")
        self.presets[name] = dict(settings if settings is not None else self.settings)
        self.active_preset = name
        self.updated_at = _now()

    def apply_preset(self, name: str) -> dict[str, Any]:
        if name not in self.presets:
            raise ProfileError(f"unknown preset: {name}")
        self.settings = dict(self.presets[name])
        self.active_preset = name
        self.updated_at = _now()
        return dict(self.settings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "game_id": self.game_id,
            "enabled": list(self.enabled),
            "disabled": list(self.disabled),
            "settings": dict(self.settings),
            "presets": {key: dict(value) for key, value in self.presets.items()},
            "active_preset": self.active_preset,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ModProfile":
        data = dict(data or {})
        return cls(
            name=str(data.get("name") or "").strip(),
            game_id=str(data.get("game_id") or DEFAULT_GAME_ID),
            enabled=data.get("enabled", []),
            disabled=data.get("disabled", []),
            settings=data.get("settings", {}),
            presets=data.get("presets", {}),
            active_preset=str(data.get("active_preset") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


@dataclass
class ProfileCollection:
    profiles: dict[str, ModProfile] = field(default_factory=dict)

    def get(self, name: str) -> ModProfile | None:
        return self.profiles.get(str(name).strip())

    def create(
        self,
        name: str,
        *,
        game_id: str = DEFAULT_GAME_ID,
        enabled: Iterable[str] = (),
        disabled: Iterable[str] = (),
        settings: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> ModProfile:
        name = str(name or "").strip()
        if not name:
            raise ProfileError("profile name is required")
        if name in self.profiles and not overwrite:
            raise ProfileError(f"profile already exists: {name}")
        profile = ModProfile(
            name=name,
            game_id=game_id,
            enabled=list(enabled),
            disabled=list(disabled),
            settings=dict(settings or {}),
        )
        self.profiles[name] = profile
        return profile

    def delete(self, name: str) -> bool:
        return self.profiles.pop(str(name).strip(), None) is not None

    def rename(self, old: str, new: str) -> ModProfile:
        old = str(old).strip()
        new = str(new).strip()
        if old not in self.profiles:
            raise ProfileError(f"unknown profile: {old}")
        if new in self.profiles and new != old:
            raise ProfileError(f"profile already exists: {new}")
        profile = self.profiles.pop(old)
        profile.name = new
        profile.updated_at = _now()
        self.profiles[new] = profile
        return profile

    def names(self) -> list[str]:
        return sorted(self.profiles)

    def to_dict(self) -> dict[str, Any]:
        return {"profiles": [profile.to_dict() for profile in self.profiles.values()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProfileCollection":
        data = dict(data or {})
        raw = data.get("profiles", data)
        collection = cls()
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    profile = ModProfile.from_dict(item)
                    collection.profiles[profile.name] = profile
        elif isinstance(raw, dict):
            for name, item in raw.items():
                if isinstance(item, dict):
                    payload = dict(item)
                    payload.setdefault("name", name)
                    profile = ModProfile.from_dict(payload)
                    collection.profiles[profile.name] = profile
        return collection


class ModProfileStore:
    """Load and save a ``ProfileCollection`` from a JSON file."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else None
        self.collection = ProfileCollection()

    def load(self, path: str | Path | None = None) -> ProfileCollection:
        path = Path(path or self.path)
        if path is None:
            raise ProfileError("profile store path is required")
        self.path = path
        if not path.exists():
            self.collection = ProfileCollection()
            return self.collection
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ProfileError(f"cannot read profiles: {exc}") from exc
        self.collection = ProfileCollection.from_dict(data)
        return self.collection

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path or self.path)
        if path is None:
            raise ProfileError("profile store path is required")
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.collection.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        return path

    def create(self, *args: Any, **kwargs: Any) -> ModProfile:
        profile = self.collection.create(*args, **kwargs)
        return profile

    def delete(self, name: str) -> bool:
        return self.collection.delete(name)

    def rename(self, old: str, new: str) -> ModProfile:
        return self.collection.rename(old, new)

    def get(self, name: str) -> ModProfile | None:
        return self.collection.get(name)

    def names(self) -> list[str]:
        return self.collection.names()

    def export_profile(self, name: str, destination: str | Path) -> Path:
        profile = self.collection.get(name)
        if profile is None:
            raise ProfileError(f"unknown profile: {name}")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            json.dump(profile.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        return destination

    def import_profile(self, source: str | Path, *, overwrite: bool = False) -> ModProfile:
        source = Path(source)
        try:
            with open(source, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ProfileError(f"cannot read profile: {exc}") from exc
        if not isinstance(data, dict):
            raise ProfileError("profile file must contain a JSON object")
        profile = ModProfile.from_dict(data)
        if profile.name in self.collection.profiles and not overwrite:
            raise ProfileError(f"profile already exists: {profile.name}")
        self.collection.profiles[profile.name] = profile
        return profile


# Module-level convenience API (names hidden tests may use).
def load_profiles(path: str | Path | None = None) -> ProfileCollection:
    store = ModProfileStore(path)
    store.load(path)
    return store.collection


def save_profiles(collection: ProfileCollection, path: str | Path) -> Path:
    store = ModProfileStore(path)
    store.collection = collection
    return store.save(path)


def create_profile(*args: Any, **kwargs: Any) -> ModProfile:
    collection = kwargs.pop("collection", None)
    if collection is None:
        collection = ProfileCollection()
    return collection.create(*args, **kwargs)


def export_profile(profile: ModProfile, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(profile.to_dict(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return destination


def import_profile(source: str | Path) -> ModProfile:
    source = Path(source)
    with open(source, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return ModProfile.from_dict(data)


__all__ = [
    "ModProfile",
    "ModProfileStore",
    "ProfileCollection",
    "ProfileError",
    "create_profile",
    "export_profile",
    "import_profile",
    "load_profiles",
    "save_profiles",
]
