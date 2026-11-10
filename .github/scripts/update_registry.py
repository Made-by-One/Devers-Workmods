#!/usr/bin/env python3
"""Apply one registry event to ``registry.json``.

Invoked by ``.github/workflows/update_registry.yml`` on a ``repository_dispatch``
event. Kept as a real script (instead of an inline ``python -c``) so the rules are
readable, testable and free of shell-quoting hazards.

Environment:
    EVENT_ACTION  add_mod | remove_mod
    PAYLOAD      JSON object from github.event.client_payload
    BOT_SECRET   shared secret configured in repository settings
    REGISTRY_PATH  optional, defaults to ./registry.json
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
DEFAULT_GAME_ID = "default"
REGISTRY_PATH = Path(os.environ.get("REGISTRY_PATH", "registry.json"))

MOD_FIELDS = (
    "id", "game_id", "name", "version", "author", "description", "repo",
    "download_url", "sha256", "icon_url", "banner_url", "entry_asset",
    "tags", "updated_at",
)


class RegistryError(ValueError):
    """The event cannot be applied to the registry."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_game_id(value: Any) -> str:
    game_id = str(value or "").strip().lower()
    if not game_id:
        return DEFAULT_GAME_ID
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in game_id)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or DEFAULT_GAME_ID


def normalize_mod(payload: dict[str, Any]) -> dict[str, Any]:
    """Whitelist and coerce a dispatch payload into a registry entry.

    The ``secret`` field is deliberately dropped: it authenticates the dispatch
    and must never be committed to a public registry file.
    """
    mod_id = str(payload.get("id") or "").strip()
    if not mod_id:
        raise RegistryError("Payload has no mod id")

    mod: dict[str, Any] = {}
    for field in MOD_FIELDS:
        value = payload.get(field, "")
        if field == "tags":
            tags = value if isinstance(value, list) else str(value or "").split(",")
            mod[field] = [str(tag).strip() for tag in tags if str(tag).strip()]
        elif field == "game_id":
            mod[field] = normalize_game_id(value)
        else:
            mod[field] = str(value or "").strip()

    mod["updated_at"] = mod["updated_at"] or now_iso()
    return mod


def authorize(payload: dict[str, Any], expected_secret: str) -> None:
    provided = str(payload.get("secret") or "")
    if not expected_secret:
        raise RegistryError("BOT_SECRET is not configured on the repository")
    if not hmac.compare_digest(provided, expected_secret):
        raise RegistryError("Invalid secret")


def load_registry(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or REGISTRY_PATH)
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "games": [], "mods": []}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        data = {"mods": data}
    if not isinstance(data, dict):
        raise RegistryError("registry.json must contain a JSON object")
    data.setdefault("mods", [])
    data.setdefault("games", [])
    if not isinstance(data["mods"], list) or not isinstance(data["games"], list):
        raise RegistryError("registry.json has an invalid shape")
    return data


def apply_event(registry: dict[str, Any], action: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return a new registry plus a human-readable summary."""
    if action not in {"add_mod", "remove_mod"}:
        raise RegistryError(f"Unsupported event: {action}")

    mods = [mod for mod in registry.get("mods", []) if isinstance(mod, dict)]
    if action == "remove_mod":
        mod_id = str(payload.get("id") or "").strip()
        if not mod_id:
            raise RegistryError("remove_mod payload has no mod id")
        remaining = [mod for mod in mods if str(mod.get("id")) != mod_id]
        if len(remaining) == len(mods):
            return {**registry, "mods": remaining}, f"No mod with id {mod_id} in registry"
        summary = f"Removed mod: {mod_id}"
    else:
        mod = normalize_mod(payload)
        remaining = [entry for entry in mods if str(entry.get("id")) != mod["id"]]
        remaining.append(mod)
        summary = f"Added/updated mod: {mod['id']} ({mod['game_id']})"

    remaining.sort(key=lambda entry: (normalize_game_id(entry.get("game_id")), str(entry.get("name", "")).lower(), str(entry.get("id"))))
    result = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": now_iso(),
        "games": sorted(
            [game for game in registry.get("games", []) if isinstance(game, dict) and game.get("id")],
            key=lambda game: normalize_game_id(game.get("id")),
        ),
        "mods": remaining,
    }
    return result, summary


def write_registry(registry: dict[str, Any], path: Path | None = None) -> None:
    path = Path(path or REGISTRY_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    action = os.environ.get("EVENT_ACTION", "")
    raw_payload = os.environ.get("PAYLOAD", "{}")
    expected_secret = os.environ.get("BOT_SECRET", "")

    try:
        payload = json.loads(raw_payload or "{}")
        if not isinstance(payload, dict):
            raise RegistryError("Payload must be a JSON object")
        authorize(payload, expected_secret)
        registry = load_registry()
        updated, summary = apply_event(registry, action, payload)
        write_registry(updated)
    except (RegistryError, ValueError, OSError) as exc:
        print(f"Registry update failed: {exc}", file=sys.stderr)
        return 1

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
