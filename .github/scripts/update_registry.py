#!/usr/bin/env python3
"""Validate registry submissions and rebuild ``registry.json``.

``registry.json`` is a generated file. The source of truth is the
``submissions/`` directory, one JSON file per mod::

    submissions/<game_id>/<mod_id>.json

A publisher opens a pull request that adds or updates one file. CI validates
every submission file on the pull request, and a maintainer merges it. The
merge triggers :func:`rebuild`, which rewrites ``registry.json`` from all
submission files and commits the result.

Usage::

    python .github/scripts/update_registry.py validate
    python .github/scripts/update_registry.py rebuild

Environment:
    SUBMISSIONS_DIR  default ``submissions``
    REGISTRY_PATH    default ``registry.json``
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
DEFAULT_GAME_ID = "default"
SUBMISSIONS_DIR = Path(os.environ.get("SUBMISSIONS_DIR", "submissions"))
REGISTRY_PATH = Path(os.environ.get("REGISTRY_PATH", "registry.json"))

MOD_FIELDS = (
    "id", "game_id", "name", "version", "author", "description", "repo",
    "download_url", "sha256", "icon_url", "banner_url", "entry_asset",
    "tags", "updated_at",
)
SUBMISSION_FIELDS = frozenset(MOD_FIELDS) | {"submitted_by"}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
URL_HOSTS = {"github.com", "raw.githubusercontent.com", "objects.githubusercontent.com"}


class RegistryError(ValueError):
    """A submission set cannot be turned into a registry."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_game_id(value: Any) -> str:
    game_id = str(value or "").strip().lower()
    if not game_id:
        return DEFAULT_GAME_ID
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in game_id)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or DEFAULT_GAME_ID


def _is_https_github(url: str) -> bool:
    if not url:
        return False
    if not url.startswith("https://"):
        return False
    host = url.split("/", 3)[2].split(":", 1)[0].lower()
    return host in URL_HOSTS


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


def validate_submission(data: Any, path: Path, root: Path) -> list[str]:
    """Return every problem with one submission file (empty means valid)."""
    errors: list[str] = []
    rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)

    def fail(message: str) -> None:
        errors.append(f"{rel}: {message}")

    if not isinstance(data, dict):
        fail("must be a JSON object")
        return errors

    unknown = sorted(set(data) - SUBMISSION_FIELDS)
    if unknown:
        fail(f"unknown field(s): {', '.join(unknown)}")

    mod_id = str(data.get("id") or "").strip()
    if not mod_id:
        fail("missing 'id'")
    elif not ID_RE.match(mod_id):
        fail("'id' must be 2-64 chars: lowercase letters, digits, '.', '_' or '-'")
    elif path.stem != mod_id:
        fail(f"file name must be '{mod_id}.json', not '{path.name}'")

    game_id = normalize_game_id(data.get("game_id"))
    folder = normalize_game_id(path.parent.name)
    if not str(data.get("game_id") or "").strip():
        fail("missing 'game_id'")
    elif game_id != folder:
        fail(f"'game_id' is '{game_id}', but the file is in submissions/{folder}/")

    name = str(data.get("name") or "").strip()
    if not name:
        fail("missing 'name'")
    elif len(name) > 120:
        fail("'name' is longer than 120 characters")

    version = str(data.get("version") or "").strip()
    if not version:
        fail("missing 'version'")
    elif len(version) > 64 or any(ch in version for ch in " /\\"):
        fail("'version' may not contain spaces or slashes")

    sha = str(data.get("sha256") or "").strip().lower()
    if not SHA_RE.match(sha):
        fail("'sha256' must be a 64-character hex digest")

    repo = str(data.get("repo") or "").strip()
    if not REPO_RE.match(repo):
        fail("'repo' must look like 'owner/name'")

    download_url = str(data.get("download_url") or "").strip()
    if not _is_https_github(download_url):
        fail("'download_url' must be an https GitHub URL")
    elif "/releases/download/" not in download_url:
        fail("'download_url' must point at a GitHub release asset")

    for field in ("icon_url", "banner_url"):
        url = str(data.get(field) or "").strip()
        if url and not _is_https_github(url):
            fail(f"'{field}' must be an https GitHub URL")

    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if not isinstance(tags, list):
        fail("'tags' must be a list of strings")
    elif len(tags) > 20:
        fail("'tags' has more than 20 entries")
    else:
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                fail("'tags' entries must be non-empty strings")
                break
            if len(tag.strip()) > 32:
                fail("'tags' entries are longer than 32 characters")
                break

    updated_at = str(data.get("updated_at") or "").strip()
    if updated_at:
        try:
            datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            fail("'updated_at' is not a valid ISO-8601 timestamp")

    return errors


def submission_files(root: Path | None = None) -> list[Path]:
    root = Path(root or SUBMISSIONS_DIR)
    if not root.is_dir():
        raise RegistryError(f"submissions directory '{root}' does not exist")
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def collect_submissions(root: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Load every submission file, returning mods plus accumulated errors."""
    root = Path(root or SUBMISSIONS_DIR)
    mods: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: dict[str, str] = {}

    for path in submission_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{path.relative_to(root).as_posix()}: invalid JSON ({exc})")
            continue
        problems = validate_submission(data, path, root)
        errors.extend(problems)
        if problems or not isinstance(data, dict):
            continue

        mod_id = str(data["id"]).strip()
        mod = {field: data.get(field, "") for field in MOD_FIELDS}
        mod["id"] = mod_id
        mod["game_id"] = normalize_game_id(mod.get("game_id"))
        mod["tags"] = mod["tags"] if isinstance(mod["tags"], list) else []
        mod["updated_at"] = str(mod.get("updated_at") or "").strip() or now_iso()
        mod["sha256"] = str(mod["sha256"]).strip().lower()

        if mod_id in seen:
            errors.append(
                f"{path.relative_to(root).as_posix()}: duplicate mod id '{mod_id}' "
                f"(also in {seen[mod_id]})"
            )
            continue
        seen[mod_id] = path.relative_to(root).as_posix()
        mods.append(mod)

    return mods, errors


def rebuild_registry(
    submissions_dir: Path | None = None,
    registry_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Build a registry document from submissions; raise on invalid input."""
    mods, errors = collect_submissions(submissions_dir)
    if errors:
        raise RegistryError("\n".join(errors))

    existing = load_registry(registry_path)
    games = [
        game for game in existing.get("games", [])
        if isinstance(game, dict) and game.get("id")
    ]
    games.sort(key=lambda game: normalize_game_id(game.get("id")))
    mods.sort(
        key=lambda mod: (
            mod["game_id"],
            str(mod.get("name", "")).lower(),
            mod["id"],
        )
    )
    registry = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": now_iso(),
        "games": games,
        "mods": mods,
    }
    return registry, len(mods)


def write_registry(registry: dict[str, Any], path: Path | None = None) -> None:
    path = Path(path or REGISTRY_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else "validate"
    try:
        if command == "validate":
            _mods, errors = collect_submissions()
            if errors:
                print("Invalid submissions:", file=sys.stderr)
                for error in errors:
                    print(f"  - {error}", file=sys.stderr)
                return 1
            files = submission_files()
            print(f"{len(files)} submission file(s) are valid.")
            return 0
        if command == "rebuild":
            registry, count = rebuild_registry()
            write_registry(registry)
            print(f"registry.json rebuilt with {count} mod(s).")
            return 0
        raise RegistryError(f"Unknown command: {command}")
    except (RegistryError, OSError, ValueError) as exc:
        print(f"Registry update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
