"""Tests for the bot that applies repository_dispatch events to registry.json."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "update_registry.py"
spec = importlib.util.spec_from_file_location("update_registry", SCRIPT)
update_registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_registry)


def test_invalid_secret_is_rejected():
    with pytest.raises(update_registry.RegistryError):
        update_registry.authorize({"secret": "wrong"}, "right")


def test_missing_configured_secret_is_rejected():
    with pytest.raises(update_registry.RegistryError):
        update_registry.authorize({"secret": "anything"}, "")


def test_add_mod_strips_secret_and_normalizes_game():
    registry = {"schema_version": 2, "games": [], "mods": []}
    payload = {
        "secret": "top-secret",
        "id": "abc",
        "game_id": "Space Rangers!",
        "name": "Neon UI",
        "version": "1.0.0",
        "tags": "ui, hud",
    }

    updated, summary = update_registry.apply_event(registry, "add_mod", payload)

    mod = updated["mods"][0]
    assert mod["game_id"] == "space-rangers"
    assert mod["tags"] == ["ui", "hud"]
    assert "secret" not in mod
    assert "secret" not in json.dumps(updated)
    assert updated["schema_version"] == 2
    assert updated["updated_at"]
    assert "abc" in summary


def test_add_mod_replaces_existing_entry_and_sorts():
    registry = {
        "mods": [
            {"id": "b", "game_id": "game-b", "name": "Beta", "version": "0.1"},
            {"id": "a", "game_id": "game-a", "name": "Alpha", "version": "0.1"},
        ]
    }

    updated, _ = update_registry.apply_event(
        registry, "add_mod", {"id": "b", "game_id": "game-b", "name": "Beta", "version": "0.2"}
    )

    assert [mod["id"] for mod in updated["mods"]] == ["a", "b"]
    assert updated["mods"][1]["version"] == "0.2"


def test_remove_mod():
    registry = {
        "mods": [
            {"id": "a", "game_id": "game-a", "name": "Alpha"},
            {"id": "b", "game_id": "game-b", "name": "Beta"},
        ]
    }

    updated, summary = update_registry.apply_event(registry, "remove_mod", {"id": "a"})

    assert [mod["id"] for mod in updated["mods"]] == ["b"]
    assert "Removed" in summary


def test_remove_missing_mod_is_a_no_op():
    registry = {"mods": [{"id": "b", "game_id": "game-b", "name": "Beta"}]}
    updated, summary = update_registry.apply_event(registry, "remove_mod", {"id": "a"})
    assert updated["mods"][0]["id"] == "b"
    assert "No mod" in summary


def test_add_without_id_fails():
    with pytest.raises(update_registry.RegistryError):
        update_registry.apply_event({"mods": []}, "add_mod", {"name": "No id"})


def test_unsupported_event_fails():
    with pytest.raises(update_registry.RegistryError):
        update_registry.apply_event({"mods": []}, "delete_everything", {"id": "a"})


def test_main_writes_registry_and_fails_on_bad_secret(tmp_path, monkeypatch):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"mods": []}', encoding="utf-8")
    payload = json.dumps({"secret": "s", "id": "x", "name": "X", "version": "1"})

    monkeypatch.setattr(update_registry, "REGISTRY_PATH", registry_path)
    monkeypatch.setenv("EVENT_ACTION", "add_mod")
    monkeypatch.setenv("PAYLOAD", payload)
    monkeypatch.setenv("BOT_SECRET", "s")
    assert update_registry.main() == 0
    saved = json.loads(registry_path.read_text(encoding="utf-8"))
    assert saved["mods"][0]["id"] == "x"
    assert "secret" not in registry_path.read_text(encoding="utf-8")

    monkeypatch.setenv("BOT_SECRET", "different")
    assert update_registry.main() == 1
