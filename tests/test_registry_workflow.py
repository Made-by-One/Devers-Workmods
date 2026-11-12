"""Tests for the bot that validates submissions and rebuilds registry.json."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "update_registry.py"
spec = importlib.util.spec_from_file_location("update_registry", SCRIPT)
update_registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_registry)

SHA = "a" * 64


def valid_mod(**overrides):
    mod = {
        "id": "abc12345",
        "game_id": "space-rangers",
        "name": "Neon UI",
        "version": "1.2.0",
        "author": "someone",
        "description": "Neon HUD",
        "repo": "someone/neon-ui",
        "download_url": (
            "https://github.com/someone/neon-ui/releases/download/v1.2.0/abc12345.zip"
        ),
        "sha256": SHA,
        "entry_asset": "NeonHud",
        "tags": ["ui", "hud"],
        "icon_url": "https://raw.githubusercontent.com/someone/neon-ui/main/icon.png",
        "banner_url": "",
        "updated_at": "2026-11-12T00:00:00+00:00",
        "submitted_by": "someone",
    }
    mod.update(overrides)
    return mod


def write_submission(root: Path, data, game="space-rangers", filename=None) -> Path:
    path = root / game / (filename or f"{data['id']}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_valid_submission_passes(tmp_path):
    path = write_submission(tmp_path, valid_mod())
    assert update_registry.validate_submission(json.loads(path.read_text()), path, tmp_path) == []
    mods, errors = update_registry.collect_submissions(tmp_path)
    assert errors == []
    assert mods[0]["game_id"] == "space-rangers"
    assert mods[0]["sha256"] == SHA


def test_filename_must_match_id(tmp_path):
    path = write_submission(tmp_path, valid_mod(), filename="other.json")
    errors = update_registry.validate_submission(json.loads(path.read_text()), path, tmp_path)
    assert any("file name must be" in error for error in errors)


def test_game_folder_must_match_game_id(tmp_path):
    path = write_submission(tmp_path, valid_mod(), game="another-game")
    errors = update_registry.validate_submission(json.loads(path.read_text()), path, tmp_path)
    assert any("file is in submissions/" in error for error in errors)


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"sha256": "not-a-hash"}, "'sha256'"),
        ({"download_url": "https://example.com/mod.zip"}, "'download_url'"),
        ({"version": "1.0 beta"}, "'version'"),
        ({"id": "ABC12345"}, "'id'"),
        ({"name": ""}, "'name'"),
        ({"tags": ["x" * 40]}, "'tags'"),
        ({"updated_at": "yesterday"}, "'updated_at'"),
    ],
)
def test_invalid_fields_are_reported(tmp_path, override, expected):
    path = write_submission(tmp_path, valid_mod(**override), filename=f"{valid_mod()['id']}.json")
    errors = update_registry.validate_submission(json.loads(path.read_text()), path, tmp_path)
    assert any(expected in error for error in errors), errors


def test_unknown_fields_are_rejected(tmp_path):
    path = write_submission(tmp_path, valid_mod(secret="leak"))
    errors = update_registry.validate_submission(json.loads(path.read_text()), path, tmp_path)
    assert any("unknown field" in error for error in errors)


def test_duplicate_ids_across_games_are_rejected(tmp_path):
    write_submission(tmp_path, valid_mod(game_id="game-a"), game="game-a")
    write_submission(tmp_path, valid_mod(game_id="game-b"), game="game-b")
    _mods, errors = update_registry.collect_submissions(tmp_path)
    assert any("duplicate mod id" in error for error in errors)


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "space-rangers" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ not json", encoding="utf-8")
    _mods, errors = update_registry.collect_submissions(tmp_path)
    assert any("invalid JSON" in error for error in errors)


def test_missing_submissions_directory_raises(tmp_path):
    with pytest.raises(update_registry.RegistryError):
        update_registry.collect_submissions(tmp_path / "missing")


def test_rebuild_sorts_and_preserves_games(tmp_path):
    submissions = tmp_path / "submissions"
    write_submission(submissions, valid_mod(id="zzz11111"), game="space-rangers")
    write_submission(
        submissions,
        valid_mod(id="aaa11111", game_id="another-game", name="Alpha"),
        game="another-game",
    )
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "games": [{"id": "space-rangers", "name": "Space Rangers"}],
                "mods": [{"id": "legacy"}],
            }
        ),
        encoding="utf-8",
    )

    registry, count = update_registry.rebuild_registry(submissions, registry_path)

    assert count == 2
    assert registry["schema_version"] == 2
    assert [mod["id"] for mod in registry["mods"]] == ["aaa11111", "zzz11111"]
    assert registry["mods"][0]["game_id"] == "another-game"
    assert registry["games"] == [{"id": "space-rangers", "name": "Space Rangers"}]
    # Generated entries never carry submission-only fields.
    assert "submitted_by" not in registry["mods"][0]
    assert registry["updated_at"]


def test_rebuild_rejects_invalid_submission(tmp_path):
    write_submission(tmp_path, valid_mod(sha256="bad"), filename="abc12345.json")
    with pytest.raises(update_registry.RegistryError):
        update_registry.rebuild_registry(tmp_path, tmp_path / "registry.json")


def test_rebuild_without_files_produces_empty_registry(tmp_path):
    submissions = tmp_path / "submissions"
    submissions.mkdir()
    registry, count = update_registry.rebuild_registry(
        submissions, tmp_path / "registry.json"
    )
    assert count == 0
    assert registry["mods"] == []


def test_main_validate_and_rebuild(tmp_path, monkeypatch):
    submissions = tmp_path / "submissions"
    registry_path = tmp_path / "registry.json"
    write_submission(submissions, valid_mod())
    monkeypatch.setattr(update_registry, "SUBMISSIONS_DIR", submissions)
    monkeypatch.setattr(update_registry, "REGISTRY_PATH", registry_path)

    assert update_registry.main(["validate"]) == 0
    assert update_registry.main(["rebuild"]) == 0

    saved = json.loads(registry_path.read_text(encoding="utf-8"))
    assert saved["mods"][0]["id"] == "abc12345"
    assert "submitted_by" not in registry_path.read_text(encoding="utf-8")

    write_submission(submissions, valid_mod(sha256="bad"))
    assert update_registry.main(["validate"]) == 1


def test_main_rejects_unknown_command(tmp_path, monkeypatch):
    monkeypatch.setattr(update_registry, "SUBMISSIONS_DIR", tmp_path)
    assert update_registry.main(["nonsense"]) == 1
